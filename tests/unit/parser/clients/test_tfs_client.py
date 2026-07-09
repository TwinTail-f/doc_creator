"""
Юнит-тесты для autodoc/parser/clients/tfs_client.py.

Весь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.
"""

import json
from unittest.mock import MagicMock

import pytest
import requests

from autodoc.exceptions import NetworkError
from autodoc.parser.clients.tfs_client import TFSClient
from autodoc.parser.clients.tfs_client_protocol import TFSClientProtocol

TFS_URL: str = "https://tfs.example.com"
BRANCH: str = "develop"
REMOTE_PATH: str = "/platform/manifests"


def _make_response(status_code: int = 200, content: bytes = b"") -> MagicMock:
    """
    Возвращает мок requests.Response с заданным кодом статуса и содержимым.

    Args:
        status_code: HTTP-код статуса, который должен вернуть мок-ответ.
        content: Тело ответа в байтах; используется также для полей text и json().

    Returns:
        Мок объекта requests.Response с настроенными атрибутами.
    """
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.content = content
    mock_resp.text = content.decode("utf-8", errors="replace")
    try:
        mock_resp.json.return_value = json.loads(content) if content else {}
    except json.JSONDecodeError:
        mock_resp.json.side_effect = json.JSONDecodeError("", "", 0)
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _make_tfs_client(parser_config) -> TFSClient:
    """
    Создаёт TFSClient из минимальной корректной конфигурации парсера.

    Args:
        parser_config: Валидированная конфигурация парсера (фикстура).

    Returns:
        Готовый к использованию экземпляр TFSClient.
    """
    return TFSClient(parser_config)


@pytest.mark.infrastructure
def test_tfs_client_get_file_content_returns_response(mocker, parser_config) -> None:
    """TFSClient.get_file_content возвращает HTTP-ответ при успехе."""
    client = _make_tfs_client(parser_config)
    mock_resp = _make_response(status_code=200, content=b"hello")
    mocker.patch.object(client.session, "get", return_value=mock_resp)

    response = client.get_file_content(TFS_URL, "/path/file.json", BRANCH)

    assert response.status_code == 200


@pytest.mark.infrastructure
def test_tfs_client_get_file_content_raises_network_error_on_failure(mocker, parser_config) -> None:
    """TFSClient.get_file_content оборачивает RequestException в NetworkError."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(client.session, "get", side_effect=requests.RequestException("timeout"))

    with pytest.raises(NetworkError):
        client.get_file_content(TFS_URL, "/path/file.json", BRANCH)


@pytest.mark.infrastructure
def test_tfs_client_get_items_returns_item_list(mocker, parser_config) -> None:
    """TFSClient.get_items возвращает список, извлечённый из ключа 'value'."""
    items = [{"path": "/a.properties"}, {"path": "/b.properties"}]
    mock_resp = _make_response(status_code=200, content=json.dumps({"value": items}).encode())
    client = _make_tfs_client(parser_config)
    mocker.patch.object(client.session, "get", return_value=mock_resp)

    result = client.get_items(TFS_URL, BRANCH)

    assert len(result) == 2


@pytest.mark.infrastructure
def test_tfs_client_get_items_raises_network_error_on_http_error(mocker, parser_config) -> None:
    """TFSClient.get_items вызывает NetworkError, когда сессия бросает RequestException."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(
        client.session, "get", side_effect=requests.RequestException("server error")
    )

    with pytest.raises(NetworkError):
        client.get_items(TFS_URL, BRANCH)


@pytest.mark.infrastructure
def test_tfs_client_download_properties_downloads_files(mocker, parser_config, tmp_path) -> None:
    """
    download_properties записывает .properties-файлы в tmp_path и пропускает другие расширения.

    Ответ листинга содержит два элемента; записывается только .properties-файл.
    """
    client = _make_tfs_client(parser_config)

    listing_items = [
        {"path": "/platform/a.properties", "isFolder": False},
        {"path": "/platform/b.txt", "isFolder": False},
    ]
    listing_resp = _make_response(
        status_code=200,
        content=json.dumps({"value": listing_items}).encode(),
    )
    mocker.patch.object(client.session, "get", return_value=listing_resp)

    file_resp = _make_response(status_code=200, content=b"name=test")
    mocker.patch.object(client, "get_file_content", return_value=file_resp)

    client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
    )

    assert (tmp_path / "a.properties").exists()
    assert (tmp_path / "a.properties").read_text(encoding="utf-8") == "name=test"
    assert not (tmp_path / "b.txt").exists()


@pytest.mark.infrastructure
def test_tfs_client_download_properties_raises_on_listing_failure(
    mocker, parser_config, tmp_path
) -> None:
    """download_properties пробрасывает NetworkError при сбое запроса листинга."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(
        client.session,
        "get",
        side_effect=requests.RequestException("connection refused"),
    )

    with pytest.raises(NetworkError):
        client.download_properties(
            items_url=TFS_URL,
            remote_path=REMOTE_PATH,
            branch=BRANCH,
            output_dir=str(tmp_path),
        )


@pytest.mark.infrastructure
def test_tfs_client_download_properties_continues_after_single_file_failure(
    mocker, parser_config, tmp_path
) -> None:
    """Сбой скачивания одного .properties-файла не прерывает загрузку остальных файлов из списка."""
    client = _make_tfs_client(parser_config)

    listing_items = [
        {"path": "/platform/broken.properties", "isFolder": False},
        {"path": "/platform/ok.properties", "isFolder": False},
    ]
    listing_resp = _make_response(
        status_code=200,
        content=json.dumps({"value": listing_items}).encode(),
    )
    mocker.patch.object(client.session, "get", return_value=listing_resp)

    ok_resp = _make_response(status_code=200, content=b"name=ok")
    mocker.patch.object(
        client,
        "get_file_content",
        side_effect=[requests.RequestException("boom"), ok_resp],
    )

    client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
    )

    assert not (tmp_path / "broken.properties").exists()
    assert (tmp_path / "ok.properties").read_text(encoding="utf-8") == "name=ok"


@pytest.mark.infrastructure
def test_tfs_client_download_properties_skips_folders(mocker, parser_config, tmp_path) -> None:
    """Элемент листинга, помеченный как папка, не скачивается, даже если его путь оканчивается на .properties."""
    client = _make_tfs_client(parser_config)

    listing_items = [
        {"path": "/platform/subdir.properties", "isFolder": True},
        {"path": "/platform/real.properties", "isFolder": False},
    ]
    listing_resp = _make_response(
        status_code=200,
        content=json.dumps({"value": listing_items}).encode(),
    )
    mocker.patch.object(client.session, "get", return_value=listing_resp)

    real_resp = _make_response(status_code=200, content=b"name=real")
    mock_get_file_content = mocker.patch.object(client, "get_file_content", return_value=real_resp)

    client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
    )

    assert not (tmp_path / "subdir.properties").exists()
    assert (tmp_path / "real.properties").read_text(encoding="utf-8") == "name=real"
    mock_get_file_content.assert_called_once()


@pytest.mark.contract
def test_tfs_client_satisfies_protocol(parser_config) -> None:
    """TFSClient структурно удовлетворяет протоколу TFSClientProtocol."""
    client = TFSClient.__new__(TFSClient)

    assert isinstance(client, TFSClientProtocol)
