"""
Тесты для autodoc.publisher.clients.confluence_transport.ConfluenceTransport.
"""
import json
from typing import Any

import pytest
import requests

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError
from autodoc.publisher.clients.confluence_transport import ConfluenceTransport

PAGE_ID: str = "123456"


def _make_response(status_code: int, body: Any = None, raw_content: bytes | None = None) -> requests.Response:
    """
    Создаёт настоящий объект ``requests.Response`` с заданным статусом и телом.

    Используется вместо ``MagicMock``, чтобы ``raise_for_status()`` и ``.json()``
    вели себя как в реальном запросе.

    Args:
        status_code: HTTP-статус ответа.
        body: Объект, который будет сериализован в JSON и помещён в тело ответа.
              Игнорируется, если передан ``raw_content``.
        raw_content: Сырые байты тела ответа (для не-JSON или пустых тел).

    Returns:
        Заполненный объект ``requests.Response``.
    """
    response = requests.Response()
    response.status_code = status_code
    if raw_content is not None:
        response._content = raw_content
    elif body is not None:
        response._content = json.dumps(body).encode("utf-8")
    else:
        response._content = b""
    return response


def _make_transport(mocker: Any, minimal_confluence_config: dict, **overrides: Any) -> ConfluenceTransport:
    """
    Создаёт ``ConfluenceTransport`` поверх переданного (при необходимости —
    переопределённого) минимального конфига Confluence.

    Args:
        mocker: Фикстура pytest-mock (не используется напрямую, оставлена
                для единообразия сигнатур хелперов в файле).
        minimal_confluence_config: Базовый словарь конфигурации.
        **overrides: Поля, переопределяющие значения из базового словаря.

    Returns:
        Готовый к использованию экземпляр ``ConfluenceTransport``.
    """
    config_dict = {**minimal_confluence_config, **overrides}
    config = ConfluenceConfigSchema(**config_dict)
    return ConfluenceTransport(config)



@pytest.mark.infrastructure
def test_happy_path_search_content_returns_results(mocker: Any, minimal_confluence_config: dict) -> None:
    """search_content возвращает список results и делает GET-запрос с правильными параметрами."""
    transport = _make_transport(mocker, minimal_confluence_config)
    response = _make_response(200, {"results": [{"id": "1"}, {"id": "2"}]})
    mock_request = mocker.patch.object(transport._session, "request", return_value=response)

    result = transport.search_content({"spaceKey": "TEST", "title": "Foo"})

    assert result == [{"id": "1"}, {"id": "2"}]
    mock_request.assert_called_once_with(
        "GET",
        f"{transport._base_url}/rest/api/content",
        params={"spaceKey": "TEST", "title": "Foo"},
    )


@pytest.mark.infrastructure
def test_happy_path_get_content_returns_raw_page(mocker: Any, minimal_confluence_config: dict) -> None:
    """get_content возвращает сырой JSON страницы и подставляет её id в URL и expand в параметры."""
    transport = _make_transport(mocker, minimal_confluence_config)
    page_json = {"id": PAGE_ID, "title": "Some Page"}
    response = _make_response(200, page_json)
    mock_request = mocker.patch.object(transport._session, "request", return_value=response)

    result = transport.get_content(PAGE_ID, expand="body.storage")

    assert result == page_json
    mock_request.assert_called_once_with(
        "GET",
        f"{transport._base_url}/rest/api/content/{PAGE_ID}",
        params={"expand": "body.storage"},
    )


@pytest.mark.infrastructure
def test_happy_path_create_content_posts_payload(mocker: Any, minimal_confluence_config: dict) -> None:
    """create_content отправляет POST с переданным payload и возвращает JSON созданной страницы."""
    transport = _make_transport(mocker, minimal_confluence_config)
    created_page = {"id": PAGE_ID, "title": "New Page"}
    response = _make_response(201, created_page)
    mock_request = mocker.patch.object(transport._session, "request", return_value=response)
    payload = {"title": "New Page", "type": "page"}

    result = transport.create_content(payload, title="New Page")

    assert result == created_page
    mock_request.assert_called_once_with(
        "POST",
        f"{transport._base_url}/rest/api/content",
        json=payload,
    )


@pytest.mark.infrastructure
def test_happy_path_update_content_puts_payload(mocker: Any, minimal_confluence_config: dict) -> None:
    """update_content отправляет PUT по URL страницы и возвращает JSON обновлённой страницы."""
    transport = _make_transport(mocker, minimal_confluence_config)
    updated_page = {"id": PAGE_ID, "title": "Updated Page"}
    response = _make_response(200, updated_page)
    mock_request = mocker.patch.object(transport._session, "request", return_value=response)
    payload = {"title": "Updated Page", "version": {"number": 2}}

    result = transport.update_content(PAGE_ID, payload, title="Updated Page")

    assert result == updated_page
    mock_request.assert_called_once_with(
        "PUT",
        f"{transport._base_url}/rest/api/content/{PAGE_ID}",
        json=payload,
    )


@pytest.mark.infrastructure
def test_http_errors_with_json_body_extracts_message(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """При HTTP-ошибке с JSON-телом текст из поля message попадает в итоговую ConfluenceError."""
    transport = _make_transport(mocker, minimal_confluence_config)
    response = _make_response(403, {"message": "Permission denied"})
    mocker.patch.object(transport._session, "request", return_value=response)

    with pytest.raises(ConfluenceError) as exc_info:
        transport.search_content({"spaceKey": "TEST"})

    message = str(exc_info.value)
    assert "HTTP-ошибка при поиске страницы" in message
    assert "Permission denied" in message


@pytest.mark.infrastructure
def test_http_errors_with_non_json_body_omits_detail(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """При HTTP-ошибке с не-JSON телом ConfluenceError всё равно поднимается, без падения на разборе тела."""
    transport = _make_transport(mocker, minimal_confluence_config)
    response = _make_response(500, raw_content=b"not json at all")
    mocker.patch.object(transport._session, "request", return_value=response)

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
def test_http_errors_network_failure_wrapped_in_confluence_error(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """Сетевой сбой (без HTTP-ответа) оборачивается в ConfluenceError с сохранением исходной причины."""
    transport = _make_transport(mocker, minimal_confluence_config)
    original_error = requests.exceptions.ConnectionError("VPN моргнул")
    mocker.patch.object(transport._session, "request", side_effect=original_error)

    with pytest.raises(ConfluenceError) as exc_info:
        transport.search_content({"spaceKey": "TEST"})

    assert "Сетевая ошибка при поиске страницы" in str(exc_info.value)
    assert exc_info.value.__cause__ is original_error


@pytest.mark.infrastructure
def test_create_session_sets_bearer_auth_header(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """_create_session прописывает Bearer-токен из конфигурации в заголовок Authorization."""
    token = "super-secret-token"
    transport = _make_transport(mocker, minimal_confluence_config, token=token)

    assert transport._session.headers["Authorization"] == f"Bearer {token}"


@pytest.mark.infrastructure
def test_create_session_respects_verify_ssl_true_and_timeout(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """При verify_ssl=True сессия проверяет сертификаты и получает настроенный таймаут."""
    transport = _make_transport(
        mocker, minimal_confluence_config, verify_ssl=True, confluence_request_timeout=45
    )

    assert transport._session.verify is True
    assert transport._session._timeout == 45


@pytest.mark.infrastructure
def test_create_session_logs_warning_when_verify_ssl_false(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """При verify_ssl=False отключение проверки SSL — намеренное поведение, о котором предупреждает лог."""
    mock_warning = mocker.patch("autodoc.publisher.clients.confluence_transport.logger.warning")

    transport = _make_transport(mocker, minimal_confluence_config, verify_ssl=False)

    assert transport._session.verify is False
    mock_warning.assert_called_once()
    warning_text = mock_warning.call_args[0][0]
    assert "SSL" in warning_text
    assert "MITM" in warning_text


@pytest.mark.infrastructure
def test_create_session_configures_retry_parameters(
    mocker: Any, minimal_confluence_config: dict
) -> None:
    """_create_session передаёт в create_bearer_session параметры ретраев и таймаута из конфигурации."""
    mock_create_bearer_session = mocker.patch(
        "autodoc.publisher.clients.confluence_transport.create_bearer_session",
        wraps=None,
    )
    mock_create_bearer_session.return_value.headers = {}

    _make_transport(mocker, minimal_confluence_config, confluence_request_timeout=60)

    mock_create_bearer_session.assert_called_once()
    _, kwargs = mock_create_bearer_session.call_args
    assert kwargs["max_retries"] == 3
    assert kwargs["backoff_factor"] == 1.0
    assert kwargs["timeout"] == 60
