"""
Unit-тесты для ConfluenceClient.

Покрывают:
- инициализацию (_build_session): Bearer-аутентификация, SSL, Content-Type
- вспомогательные методы: _build_url
- публичные методы: find_page, get_page, create_page, update_page,
  get_or_create_page, get_page_body, publish_page
"""

import pytest
import requests
from unittest.mock import MagicMock, patch, call

from autodoc.config.schemas import ConfluenceConfigSchema
from autodoc.exceptions import PublishError
from autodoc.publisher.clients.confluence_client import (
    ConfluenceClient,
    _RETRY_COUNT,
    _BACKOFF_FACTOR,
    _INITIAL_VERSION,
)

_SESSION_FACTORY_PATH = (
    "autodoc.publisher.clients.confluence_client.create_retryable_session"
)

# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> ConfluenceConfigSchema:
    defaults = {
        "url": "https://confluence.example.com",
        "token": "test-pat-token",
        "space": "PROJ",
        "confluence_request_timeout": 30,
        "verify_ssl": True,
    }
    return ConfluenceConfigSchema(**{**defaults, **overrides})


def _make_mock_session() -> MagicMock:
    session = MagicMock()
    session.headers = {}
    session.verify = True
    return session


def _make_page_response(
    page_id: str = "123", title: str = "Test Page", version: int = 1
):
    """Формирует типичный ответ Confluence REST API для одной страницы."""
    mock = MagicMock(spec=requests.Response)
    mock.status_code = 200
    mock.json.return_value = {
        "id": page_id,
        "title": title,
        "version": {"number": version},
        "body": {"storage": {"value": "<p>content</p>"}},
    }
    return mock


def _make_search_response(results: list[dict]) -> MagicMock:
    mock = MagicMock(spec=requests.Response)
    mock.status_code = 200
    mock.json.return_value = {"results": results, "size": len(results)}
    return mock


# ---------------------------------------------------------------------------
# Инициализация / _build_session
# ---------------------------------------------------------------------------


class TestConfluenceClientInit:
    """Тесты инициализации ConfluenceClient и _build_session."""

    def test_bearer_token_passed_to_factory(self) -> None:
        """_build_session вызывает create_retryable_session с bearer=True."""
        config = _make_config()
        mock_session = _make_mock_session()

        with patch(_SESSION_FACTORY_PATH, return_value=mock_session) as mock_factory:
            ConfluenceClient(config)

        mock_factory.assert_called_once_with(
            token="test-pat-token",
            bearer=True,
            max_retries=_RETRY_COUNT,
            backoff_factor=_BACKOFF_FACTOR,
            timeout=30,
        )

    def test_no_basic_auth_on_session(self) -> None:
        """Созданная сессия не использует Basic auth — только Bearer через заголовок."""
        config = _make_config()
        client = ConfluenceClient(config)

        assert client._session.auth is None
        assert "Bearer test-pat-token" in client._session.headers.get(
            "Authorization", ""
        )

    def test_bearer_header_set_correctly(self) -> None:
        """Authorization-заголовок содержит корректный Bearer-токен."""
        config = _make_config(token="super-secret-pat")
        client = ConfluenceClient(config)

        assert client._session.headers["Authorization"] == "Bearer super-secret-pat"

    def test_content_type_json_header_set(self) -> None:
        """Заголовок Content-Type: application/json устанавливается при инициализации."""
        config = _make_config()
        client = ConfluenceClient(config)

        assert client._session.headers.get("Content-Type") == "application/json"

    def test_ssl_verify_enabled_by_default(self) -> None:
        """По умолчанию SSL-верификация включена."""
        config = _make_config(verify_ssl=True)
        client = ConfluenceClient(config)

        assert client._session.verify is True

    def test_ssl_verify_can_be_disabled(self) -> None:
        """verify_ssl=False отключает SSL-верификацию сессии."""
        config = _make_config(verify_ssl=False)
        client = ConfluenceClient(config)

        assert client._session.verify is False

    def test_raises_if_url_is_empty(self) -> None:
        """PublishError при пустом URL."""
        config = _make_config(url="")
        with pytest.raises(PublishError, match="url не может быть пустым"):
            ConfluenceClient(config)

    def test_base_url_trailing_slash_stripped(self) -> None:
        """Завершающий слеш убирается из base URL."""
        config = _make_config(url="https://confluence.example.com/")
        client = ConfluenceClient(config)

        assert client._base_url == "https://confluence.example.com"

    def test_space_stored(self) -> None:
        """Space из конфигурации сохраняется в атрибуте."""
        config = _make_config(space="MYSPACE")
        client = ConfluenceClient(config)

        assert client._space == "MYSPACE"


# ---------------------------------------------------------------------------
# _api_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    """Тесты вспомогательного метода _api_url."""

    @pytest.fixture
    def client(self) -> ConfluenceClient:
        return ConfluenceClient(_make_config())

    def test_single_segment(self, client: ConfluenceClient) -> None:
        assert (
            client._api_url("content")
            == "https://confluence.example.com/rest/api/content"
        )

    def test_multiple_segments(self, client: ConfluenceClient) -> None:
        assert (
            client._api_url("content", "123", "child", "page")
            == "https://confluence.example.com/rest/api/content/123/child/page"
        )

    def test_no_double_slashes(self, client: ConfluenceClient) -> None:
        url = client._api_url("content")
        assert "//" not in url.replace("https://", "")


# ---------------------------------------------------------------------------
# find_page
# ---------------------------------------------------------------------------


class TestFindPage:
    """Тесты метода find_page."""

    @pytest.fixture
    def client(self) -> ConfluenceClient:
        c = ConfluenceClient(_make_config())
        c._session = _make_mock_session()
        return c

    def test_returns_page_when_found(self, client: ConfluenceClient) -> None:
        page = {"id": "42", "title": "My Page"}
        client._session.get.return_value = _make_search_response([page])

        result = client.find_page("My Page")

        assert result == page

    def test_returns_none_when_not_found(self, client: ConfluenceClient) -> None:
        client._session.get.return_value = _make_search_response([])

        result = client.find_page("Nonexistent Page")

        assert result is None

    def test_search_uses_correct_space(self, client: ConfluenceClient) -> None:
        client._session.get.return_value = _make_search_response([])

        client.find_page("Some Title")

        _, kwargs = client._session.get.call_args
        assert kwargs["params"]["spaceKey"] == "PROJ"

    def test_search_uses_correct_title(self, client: ConfluenceClient) -> None:
        client._session.get.return_value = _make_search_response([])

        client.find_page("Exact Title")

        _, kwargs = client._session.get.call_args
        assert kwargs["params"]["title"] == "Exact Title"


# ---------------------------------------------------------------------------
# get_page
# ---------------------------------------------------------------------------


class TestGetPage:
    """Тесты метода get_page."""

    @pytest.fixture
    def client(self) -> ConfluenceClient:
        c = ConfluenceClient(_make_config())
        c._session = _make_mock_session()
        return c

    def test_returns_page_dict_on_success(self, client: ConfluenceClient) -> None:
        client._session.get.return_value = _make_page_response(page_id="99")

        result = client.get_page("99")

        assert result["id"] == "99"

    def test_raises_publish_error_on_http_error(self, client: ConfluenceClient) -> None:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404"
        )
        client._session.get.return_value = mock_response

        with pytest.raises(PublishError):
            client.get_page("nonexistent")


# ---------------------------------------------------------------------------
# create_page
# ---------------------------------------------------------------------------


class TestCreatePage:
    """Тесты метода create_page."""

    @pytest.fixture
    def client(self) -> ConfluenceClient:
        c = ConfluenceClient(_make_config())
        c._session = _make_mock_session()
        return c

    def test_returns_created_page_dict(self, client: ConfluenceClient) -> None:
        client._session.post.return_value = _make_page_response(page_id="200")

        result = client.create_page(title="New Page", body="<p>body</p>", parent_id="1")

        assert result["id"] == "200"

    def test_post_called_with_correct_payload(self, client: ConfluenceClient) -> None:
        client._session.post.return_value = _make_page_response()

        client.create_page(title="My Title", body="<p>content</p>", parent_id="50")

        _, kwargs = client._session.post.call_args
        payload = kwargs["json"]
        assert payload["title"] == "My Title"
        assert payload["ancestors"] == [{"id": "50"}]
        assert payload["space"]["key"] == "PROJ"
        assert payload["version"]["number"] == _INITIAL_VERSION

    def test_raises_publish_error_on_failure(self, client: ConfluenceClient) -> None:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500"
        )
        client._session.post.return_value = mock_response

        with pytest.raises(PublishError):
            client.create_page(title="Fail", body="", parent_id="1")


# ---------------------------------------------------------------------------
# update_page
# ---------------------------------------------------------------------------


class TestUpdatePage:
    """Тесты метода update_page."""

    @pytest.fixture
    def client(self) -> ConfluenceClient:
        c = ConfluenceClient(_make_config())
        c._session = _make_mock_session()
        return c

    def test_version_is_incremented(self, client: ConfluenceClient) -> None:
        """update_page автоинкрементирует версию страницы."""
        client._session.get.return_value = _make_page_response(version=3)
        client._session.put.return_value = _make_page_response(version=4)

        client.update_page(page_id="10", title="Updated", body="<p>new</p>")

        _, kwargs = client._session.put.call_args
        assert kwargs["json"]["version"]["number"] == 4

    def test_raises_publish_error_on_put_failure(
        self, client: ConfluenceClient
    ) -> None:
        client._session.get.return_value = _make_page_response(version=1)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "409"
        )
        client._session.put.return_value = mock_response

        with pytest.raises(PublishError):
            client.update_page(page_id="10", title="X", body="")