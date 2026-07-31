"""
Тесты для autodoc.publisher.clients.confluence_transport.ConfluenceTransport.
"""

from typing import Any

import pytest
import requests
import responses
from pytest_mock import MockerFixture
from responses import matchers

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError
from autodoc.publisher.clients.confluence_transport import ConfluenceTransport

PAGE_ID: str = "123456"


def _make_transport(minimal_confluence_config: dict, **overrides: Any) -> ConfluenceTransport:
    """
    Создаёт ``ConfluenceTransport`` поверх переданного (при необходимости —
    переопределённого) минимального конфига Confluence.

    Args:
        minimal_confluence_config: Базовый словарь конфигурации.
        **overrides: Поля, переопределяющие значения из базового словаря.

    Returns:
        Готовый к использованию экземпляр ``ConfluenceTransport``.
    """
    config_dict = {**minimal_confluence_config, **overrides}
    config = ConfluenceConfigSchema(**config_dict)
    return ConfluenceTransport(config)


@pytest.mark.infrastructure
@responses.activate
def test_happy_path_search_content_returns_results(minimal_confluence_config: dict) -> None:
    """search_content возвращает список results и делает GET-запрос с правильными параметрами."""
    transport = _make_transport(minimal_confluence_config)
    responses.add(
        responses.GET,
        f"{transport._base_url}/rest/api/content",
        json={"results": [{"id": "1"}, {"id": "2"}]},
        status=200,
        match=[matchers.query_param_matcher({"spaceKey": "TEST", "title": "Foo"})],
    )

    result = transport.search_content({"spaceKey": "TEST", "title": "Foo"})

    assert result == [{"id": "1"}, {"id": "2"}]


@pytest.mark.infrastructure
@responses.activate
def test_happy_path_get_content_returns_raw_page(minimal_confluence_config: dict) -> None:
    """get_content возвращает сырой JSON страницы и подставляет её id в URL и expand в параметры."""
    transport = _make_transport(minimal_confluence_config)
    page_json = {"id": PAGE_ID, "title": "Some Page"}
    responses.add(
        responses.GET,
        f"{transport._base_url}/rest/api/content/{PAGE_ID}",
        json=page_json,
        status=200,
        match=[matchers.query_param_matcher({"expand": "body.storage"})],
    )

    result = transport.get_content(PAGE_ID, expand="body.storage")

    assert result == page_json


@pytest.mark.infrastructure
@responses.activate
def test_happy_path_create_content_posts_payload(minimal_confluence_config: dict) -> None:
    """create_content отправляет POST с переданным payload и возвращает JSON созданной страницы."""
    transport = _make_transport(minimal_confluence_config)
    created_page = {"id": PAGE_ID, "title": "New Page"}
    payload = {"title": "New Page", "type": "page"}
    responses.add(
        responses.POST,
        f"{transport._base_url}/rest/api/content",
        json=created_page,
        status=201,
        match=[matchers.json_params_matcher(payload)],
    )

    result = transport.create_content(payload, title="New Page")

    assert result == created_page


@pytest.mark.infrastructure
@responses.activate
def test_happy_path_update_content_puts_payload(minimal_confluence_config: dict) -> None:
    """update_content отправляет PUT по URL страницы и возвращает JSON обновлённой страницы."""
    transport = _make_transport(minimal_confluence_config)
    updated_page = {"id": PAGE_ID, "title": "Updated Page"}
    payload = {"title": "Updated Page", "version": {"number": 2}}
    responses.add(
        responses.PUT,
        f"{transport._base_url}/rest/api/content/{PAGE_ID}",
        json=updated_page,
        status=200,
        match=[matchers.json_params_matcher(payload)],
    )

    result = transport.update_content(PAGE_ID, payload, title="Updated Page")

    assert result == updated_page


@pytest.mark.infrastructure
@responses.activate
def test_http_errors_with_json_body_extracts_message(minimal_confluence_config: dict) -> None:
    """При HTTP-ошибке с JSON-телом текст из поля message попадает в итоговую ConfluenceError."""
    transport = _make_transport(minimal_confluence_config)
    responses.add(
        responses.GET,
        f"{transport._base_url}/rest/api/content",
        json={"message": "Permission denied"},
        status=403,
    )

    with pytest.raises(ConfluenceError) as exc_info:
        transport.search_content({"spaceKey": "TEST"})

    message = str(exc_info.value)
    assert "HTTP-ошибка при поиске страницы" in message
    assert "Permission denied" in message


@pytest.mark.infrastructure
@responses.activate
def test_http_errors_with_non_json_body_omits_detail(minimal_confluence_config: dict) -> None:
    """При HTTP-ошибке с не-JSON телом ConfluenceError всё равно поднимается, без падения на разборе тела."""
    transport = _make_transport(minimal_confluence_config)
    # 400, а не 500: 500 входит в _RETRY_STATUS_CODES (см. retryable_session.py),
    # поэтому сессия исчерпала бы повторные попытки и подняла бы сетевую
    # ошибку retry-адаптера вместо HTTPError с этим телом ответа — тест
    # проверял бы не тот путь кода.
    responses.add(
        responses.GET,
        f"{transport._base_url}/rest/api/content",
        body=b"not json at all",
        status=400,
    )

    with pytest.raises(ConfluenceError) as exc_info:
        transport.search_content({"spaceKey": "TEST"})

    message = str(exc_info.value)
    assert "HTTP-ошибка при поиске страницы" in message
    assert "Traceback" not in message
    assert "JSONDecodeError" not in message


@pytest.mark.infrastructure
def test_http_errors_extract_error_detail_with_none_response_returns_empty_string() -> None:
    """_extract_error_detail не падает и возвращает пустую строку, если ответа не было вовсе."""
    assert ConfluenceTransport._extract_error_detail(None) == ""


@pytest.mark.infrastructure
@responses.activate
def test_http_errors_network_failure_wrapped_in_confluence_error(
    minimal_confluence_config: dict,
) -> None:
    """Сетевой сбой (без HTTP-ответа) оборачивается в ConfluenceError с сохранением исходной причины."""
    transport = _make_transport(minimal_confluence_config)
    original_error = requests.exceptions.ConnectionError("VPN моргнул")
    responses.add(
        responses.GET,
        f"{transport._base_url}/rest/api/content",
        body=original_error,
    )

    with pytest.raises(ConfluenceError) as exc_info:
        transport.search_content({"spaceKey": "TEST"})

    assert "Сетевая ошибка при поиске страницы" in str(exc_info.value)
    assert exc_info.value.__cause__ is original_error


@pytest.mark.infrastructure
def test_create_session_sets_bearer_auth_header(minimal_confluence_config: dict) -> None:
    """_create_session прописывает Bearer-токен из конфигурации в заголовок Authorization."""
    token = "super-secret-token"
    transport = _make_transport(minimal_confluence_config, token=token)

    assert transport._session.headers["Authorization"] == f"Bearer {token}"


@pytest.mark.infrastructure
def test_create_session_respects_verify_ssl_true_and_timeout(
    minimal_confluence_config: dict,
) -> None:
    """При verify_ssl=True сессия проверяет сертификаты и получает настроенный таймаут."""
    transport = _make_transport(
        minimal_confluence_config, verify_ssl=True, confluence_request_timeout=45
    )

    assert transport._session.verify is True
    assert transport._session._timeout == 45


@pytest.mark.infrastructure
def test_create_session_logs_warning_when_verify_ssl_false(
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """При verify_ssl=False отключение проверки SSL — намеренное поведение, о котором предупреждает лог."""
    mock_warning = mocker.patch("autodoc.publisher.clients.confluence_transport.logger.warning")

    transport = _make_transport(minimal_confluence_config, verify_ssl=False)

    assert transport._session.verify is False
    mock_warning.assert_called_once()
    warning_text = mock_warning.call_args[0][0]
    assert "SSL" in warning_text
    assert "MITM" in warning_text


@pytest.mark.infrastructure
def test_create_session_configures_retry_parameters(
    mocker: MockerFixture, minimal_confluence_config: dict
) -> None:
    """_create_session передаёт в create_bearer_session параметры ретраев и таймаута из конфигурации."""
    mock_create_bearer_session = mocker.patch(
        "autodoc.publisher.clients.confluence_transport.create_bearer_session",
    )
    mock_create_bearer_session.return_value.headers = {}

    _make_transport(minimal_confluence_config, confluence_request_timeout=60)

    mock_create_bearer_session.assert_called_once()
    _, kwargs = mock_create_bearer_session.call_args
    assert kwargs["max_retries"] == 3
    assert kwargs["backoff_factor"] == 1.0
    assert kwargs["timeout"] == 60
