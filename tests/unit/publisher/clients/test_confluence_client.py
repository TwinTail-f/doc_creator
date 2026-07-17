"""
Тесты для autodoc.publisher.clients.confluence_client.ConfluenceClient.

Стратегия тестирования:
- ConfluenceClient делегирует все HTTP-вызовы экземпляру ConfluenceTransport
  (self._transport). Сам ConfluenceTransport полностью мокается через
  mocker.patch на импорт класса ConfluenceTransport в confluence_client,
  поэтому реальная HTTP-сессия и сетевые вызовы не используются.
- Объект mock_transport предоставляет управляемые ответы search_content /
  get_content / create_content / update_content (сырые JSON-словари,
  соответствующие публичному контракту ConfluenceTransport).
- Фикстура minimal_confluence_config приходит из tests/unit/publisher/conftest.py.
"""
from typing import Any

import pytest

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError, PublishError
from autodoc.publisher.clients.confluence_client import ConfluenceClient

SPACE: str = "TEST"
PAGE_TITLE: str = "Test Page"
PAGE_BODY: str = "<p>Content</p>"
PAGE_ID: str = "123456"
PARENT_ID: str = "root-001"


@pytest.fixture
def confluence_client(minimal_confluence_config: dict, mocker: Any) -> ConfluenceClient:
    """ConfluenceClient с полностью замоканным ConfluenceTransport."""
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
    """ConfluenceClient, настроенный с title_conflict_policy='move' через публичный конфиг.

    Собирает его через ConfluenceConfigSchema, а не прямой подменой приватного 
    атрибута _title_conflict_policy, чтобы тест проверял реальный путь, управляемый 
    конфигурацией.
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


@pytest.mark.contract
def test_find_page_returns_none_when_not_found(confluence_client: ConfluenceClient) -> None:
    """find_page возвращает None, если транспорт вернул пустой список результатов."""
    confluence_client._mock_transport.search_content.return_value = []
    result = confluence_client.find_page(PAGE_TITLE, space=SPACE)
    assert result is None


@pytest.mark.contract
def test_find_page_returns_page_dict_when_found(confluence_client: ConfluenceClient) -> None:
    """find_page возвращает ConfluencePage, построенный из первого результата, если страница существует."""
    page_data = {"id": PAGE_ID, "title": PAGE_TITLE}
    confluence_client._mock_transport.search_content.return_value = [page_data]
    result = confluence_client.find_page(PAGE_TITLE, space=SPACE)
    assert result is not None
    assert result.id == PAGE_ID
    assert result.title == PAGE_TITLE


@pytest.mark.infrastructure
def test_get_page_returns_raw_page_dict(confluence_client: ConfluenceClient) -> None:
    """get_page возвращает ConfluencePage, построенный из ответа транспорта по ID страницы."""
    page_data = {"id": PAGE_ID, "title": PAGE_TITLE, "version": {"number": 3}}
    confluence_client._mock_transport.get_content.return_value = page_data
    result = confluence_client.get_page(PAGE_ID)
    assert result.id == PAGE_ID
    assert result.title == PAGE_TITLE
    assert result.version == 3


@pytest.mark.contract
def test_get_page_body_returns_empty_string_when_page_not_found(
    confluence_client: ConfluenceClient,
) -> None:
    """get_page_body возвращает '', если страница не найдена."""
    confluence_client._mock_transport.search_content.return_value = []
    result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE)
    assert result == ""


@pytest.mark.contract
def test_get_page_body_returns_body_when_page_exists(confluence_client: ConfluenceClient) -> None:
    """get_page_body возвращает значение storage, если страница существует."""
    page_data = {
        "id": PAGE_ID,
        "title": PAGE_TITLE,
        "body": {"storage": {"value": "<p>html</p>"}},
    }
    confluence_client._mock_transport.search_content.return_value = [page_data]
    result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE)
    assert result == "<p>html</p>"


@pytest.mark.business_logic
def test_get_page_body_returns_empty_when_found_in_wrong_subtree(
    confluence_client: ConfluenceClient,
) -> None:
    """get_page_body возвращает '', если страница с таким заголовком найдена под другим предком."""
    wrong_parent = "wrong-parent-777"
    page_data = {
        "id": PAGE_ID,
        "title": PAGE_TITLE,
        "body": {"storage": {"value": "<p>html</p>"}},
        "ancestors": [{"id": wrong_parent}],
    }
    confluence_client._mock_transport.search_content.return_value = [page_data]
    result = confluence_client.get_page_body(space=SPACE, title=PAGE_TITLE, parent_id=PARENT_ID)
    assert result == ""


class TestPublishPage:
    """Тесты для ConfluenceClient.publish_page()."""

    def _setup_not_found_then_created(self, confluence_client: ConfluenceClient) -> None:
        """Настраивает мок так, что find_page возвращает None, а create_page — успешно."""
        confluence_client._mock_transport.search_content.return_value = []
        confluence_client._mock_transport.create_content.return_value = {"id": PAGE_ID}

    def _setup_existing_page(self, confluence_client: ConfluenceClient) -> None:
        """Настраивает мок так, что find_page возвращает существующую страницу, а update — успешно."""
        existing = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 3},
            "ancestors": [{"id": PARENT_ID}],
        }
        confluence_client._mock_transport.search_content.return_value = [existing]
        confluence_client._mock_transport.update_content.return_value = {"id": PAGE_ID}

    @pytest.mark.business_logic
    def test_publish_page_creates_new_page_when_not_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """Если страница не существует, вызывается create_content."""
        self._setup_not_found_then_created(confluence_client)
        confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        confluence_client._mock_transport.create_content.assert_called_once()

    @pytest.mark.business_logic
    def test_publish_page_updates_existing_page_when_exists(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """Если страница существует, вызывается update_content."""
        self._setup_existing_page(confluence_client)
        confluence_client.publish_page(
            space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE, body_html=PAGE_BODY
        )
        confluence_client._mock_transport.update_content.assert_called_once()

    @pytest.mark.contract
    def test_publish_page_returns_dict_with_id_version_status(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """publish_page возвращает PageResult с полями id, version и status."""
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
        """publish_page поднимает PublishError, если транспорт сообщил об HTTP-ошибке."""
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
        """publish_page вызывает update_content, даже если предок найденной страницы отличается (title_conflict_policy='move')."""
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
            parent_id=PARENT_ID,  # отличается от WRONG_PARENT
            title=PAGE_TITLE,
            body_html=PAGE_BODY,
        )

        confluence_client_move_policy._mock_transport.update_content.assert_called_once()

    @pytest.mark.business_logic
    def test_publish_page_raises_on_title_conflict_when_policy_is_error(
        self, confluence_client: ConfluenceClient
    ) -> None:
        """publish_page поднимает ConfluenceError при конфликте заголовка, если title_conflict_policy='error' (значение по умолчанию)."""
        WRONG_PARENT = "wrong-parent-555"

        existing_page = {
            "id": PAGE_ID,
            "title": PAGE_TITLE,
            "version": {"number": 2},
            "ancestors": [{"id": WRONG_PARENT}],
        }
        confluence_client._mock_transport.search_content.return_value = [existing_page]

        with pytest.raises(ConfluenceError):
            confluence_client.publish_page(
                space=SPACE,
                parent_id=PARENT_ID,  # отличается от WRONG_PARENT
                title=PAGE_TITLE,
                body_html=PAGE_BODY,
            )
        confluence_client._mock_transport.update_content.assert_not_called()

    @pytest.mark.business_logic
    def test_publish_page_put_payload_contains_correct_parent_id(
        self,
        confluence_client_move_policy: ConfluenceClient,
    ) -> None:
        """Payload update_content содержит ancestors[0].id, равный запрошенному parent_id, а не старому."""
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
        # _build_payload всегда устанавливает: payload["ancestors"] = [{"id": parent_id}]
        ancestors = payload.get("ancestors", [])
        assert any(
            a["id"] == NEW_PARENT for a in ancestors
        ), f"Ожидался parent_id={NEW_PARENT!r} в ancestors, получено: {ancestors}"

    @pytest.mark.business_logic
    def test_publish_page_version_incremented_on_reparent(
        self,
        confluence_client_move_policy: ConfluenceClient,
    ) -> None:
        """Номер версии корректно увеличивается (текущий+1), даже когда страница переносится под нового родителя."""
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


@pytest.mark.contract
def test_get_or_create_page_returns_id_if_page_exists(confluence_client: ConfluenceClient) -> None:
    """resolve_existing_page_id возвращает ID существующей страницы, ничего не создавая."""
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


@pytest.mark.contract
def test_get_or_create_page_creates_and_returns_id_if_not_exists(
    confluence_client: ConfluenceClient,
) -> None:
    """Если страница не найдена, resolve_existing_page_id возвращает None, а create_page нужно вызывать отдельно."""
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


@pytest.mark.business_logic
def test_resolve_existing_page_id_moves_page_and_preserves_body_when_conflict(
    confluence_client_move_policy: ConfluenceClient,
) -> None:
    """resolve_existing_page_id переносит страницу под ожидаемого родителя и сохраняет её текущее тело (перезапросив его через get_page)."""
    WRONG_PARENT = "wrong-parent-321"
    PRESERVED_BODY = "<p>Существующее содержимое</p>"

    existing_page = {
        "id": PAGE_ID,
        "title": PAGE_TITLE,
        "version": {"number": 5},
        "ancestors": [{"id": WRONG_PARENT}],
    }
    confluence_client_move_policy._mock_transport.search_content.return_value = [existing_page]
    confluence_client_move_policy._mock_transport.get_content.return_value = {
        "id": PAGE_ID,
        "title": PAGE_TITLE,
        "version": {"number": 5},
        "ancestors": [{"id": WRONG_PARENT}],
        "body": {"storage": {"value": PRESERVED_BODY}},
    }
    confluence_client_move_policy._mock_transport.update_content.return_value = {"id": PAGE_ID}

    result = confluence_client_move_policy.resolve_existing_page_id(
        space=SPACE, parent_id=PARENT_ID, title=PAGE_TITLE
    )

    assert result == PAGE_ID
    confluence_client_move_policy._mock_transport.get_content.assert_called_once()
    update_call = confluence_client_move_policy._mock_transport.update_content.call_args
    payload = update_call.args[1]
    assert payload["body"]["storage"]["value"] == PRESERVED_BODY


@pytest.mark.infrastructure
def test_confluence_client_passes_timeout_to_session(
    minimal_confluence_config: dict, mocker: Any
) -> None:
    """ConfluenceClient передаёт confluence_request_timeout в create_bearer_session через ConfluenceTransport."""
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
