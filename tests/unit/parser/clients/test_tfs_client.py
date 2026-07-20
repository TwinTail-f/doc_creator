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
from autodoc.parser.clients.tfs_client_enums import RecursionLevel, VersionType

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
    """TFSClient.get_file_content возвращает HTTP-ответ сессии без изменений."""
    client = _make_tfs_client(parser_config)
    mock_resp = _make_response(status_code=200, content=b"hello")
    mocker.patch.object(client.session, "get", return_value=mock_resp)

    response = client.get_file_content(TFS_URL, "/path/file.json", BRANCH)

    assert response is mock_resp


@pytest.mark.infrastructure
def test_tfs_client_get_file_content_raises_network_error_on_failure(mocker, parser_config) -> None:
    """TFSClient.get_file_content оборачивает RequestException в NetworkError."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(client.session, "get", side_effect=requests.RequestException("timeout"))

    with pytest.raises(NetworkError):
        client.get_file_content(TFS_URL, "/path/file.json", BRANCH)


@pytest.mark.contract
@pytest.mark.parametrize(
    "version_type, expected",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
def test_tfs_client_get_file_content_sends_version_type_in_request(
    mocker, parser_config, version_type: VersionType, expected: str
) -> None:
    """get_file_content передаёт versionDescriptor.versionType в параметрах запроса согласно переданному VersionType."""
    client = _make_tfs_client(parser_config)
    mock_resp = _make_response(status_code=200, content=b"data")
    mock_get = mocker.patch.object(client.session, "get", return_value=mock_resp)

    client.get_file_content(TFS_URL, "/path/file.json", BRANCH, version_type=version_type)

    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["versionDescriptor.versionType"] == expected


@pytest.mark.infrastructure
def test_tfs_client_get_items_returns_item_list(mocker, parser_config) -> None:
    """TFSClient.get_items возвращает список, извлечённый из ключа 'value'."""
    items = [{"path": "/a.properties"}, {"path": "/b.properties"}]
    mock_resp = _make_response(status_code=200, content=json.dumps({"value": items}).encode())
    client = _make_tfs_client(parser_config)
    mocker.patch.object(client.session, "get", return_value=mock_resp)

    result = client.get_items(TFS_URL, BRANCH)

    assert result == items


@pytest.mark.infrastructure
def test_tfs_client_get_items_raises_network_error_on_http_error(mocker, parser_config) -> None:
    """TFSClient.get_items вызывает NetworkError, когда сессия бросает RequestException."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(
        client.session, "get", side_effect=requests.RequestException("server error")
    )

    with pytest.raises(NetworkError):
        client.get_items(TFS_URL, BRANCH)


@pytest.mark.contract
@pytest.mark.parametrize(
    "version_type, expected",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
def test_tfs_client_get_items_sends_version_type_in_request(
    mocker, parser_config, version_type: VersionType, expected: str
) -> None:
    """get_items передаёт versionDescriptor.versionType в параметрах запроса согласно переданному VersionType."""
    client = _make_tfs_client(parser_config)
    mock_resp = _make_response(status_code=200, content=json.dumps({"value": []}).encode())
    mock_get = mocker.patch.object(client.session, "get", return_value=mock_resp)

    client.get_items(TFS_URL, BRANCH, version_type=version_type)

    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["versionDescriptor.versionType"] == expected


@pytest.mark.contract
@pytest.mark.parametrize(
    "recursion, expected",
    [
        pytest.param(RecursionLevel.ONE_LEVEL, "OneLevel", id="one-level"),
        pytest.param(RecursionLevel.FULL, "Full", id="full"),
    ],
)
def test_tfs_client_get_items_sends_recursion_level_in_request(
    mocker, parser_config, recursion: RecursionLevel, expected: str
) -> None:
    """get_items передаёт recursionLevel в параметрах запроса согласно переданному RecursionLevel."""
    client = _make_tfs_client(parser_config)
    mock_resp = _make_response(status_code=200, content=json.dumps({"value": []}).encode())
    mock_get = mocker.patch.object(client.session, "get", return_value=mock_resp)

    client.get_items(TFS_URL, BRANCH, recursion=recursion)

    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["recursionLevel"] == expected


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    "listing_items, skipped_name, downloaded_name, downloaded_content",
    [
        pytest.param(
            [
                {"path": "/platform/a.properties", "isFolder": False},
                {"path": "/platform/b.txt", "isFolder": False},
            ],
            "b.txt",
            "a.properties",
            "name=test",
            id="skips-non-properties-extension",
        ),
        pytest.param(
            [
                {"path": "/platform/subdir.properties", "isFolder": True},
                {"path": "/platform/real.properties", "isFolder": False},
            ],
            "subdir.properties",
            "real.properties",
            "name=real",
            id="skips-folder-flagged-item",
        ),
    ],
)
def test_tfs_client_download_properties_filters_items_before_downloading(
    mocker,
    parser_config,
    tmp_path,
    listing_items: list[dict],
    skipped_name: str,
    downloaded_name: str,
    downloaded_content: str,
) -> None:
    """
    download_properties скачивает только элементы листинга с isFolder=False и путём,
    оканчивающимся на .properties; остальные элементы (папки или иные расширения) пропускаются.
    """
    client = _make_tfs_client(parser_config)
    listing_resp = _make_response(
        status_code=200,
        content=json.dumps({"value": listing_items}).encode(),
    )
    mocker.patch.object(client.session, "get", return_value=listing_resp)

    file_resp = _make_response(status_code=200, content=downloaded_content.encode())
    mock_get_file_content = mocker.patch.object(client, "get_file_content", return_value=file_resp)

    client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
    )

    assert (tmp_path / downloaded_name).read_text(encoding="utf-8") == downloaded_content
    assert not (tmp_path / skipped_name).exists()
    mock_get_file_content.assert_called_once()


@pytest.mark.contract
@pytest.mark.parametrize(
    "version_type, expected_version_type",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
def test_tfs_client_download_properties_lists_with_correct_request_params(
    mocker, parser_config, tmp_path, version_type: VersionType, expected_version_type: str
) -> None:
    """
    download_properties запрашивает листинг файлов с recursionLevel=OneLevel (фиксировано)
    и versionDescriptor.versionType согласно переданному version_type.
    """
    client = _make_tfs_client(parser_config)
    listing_resp = _make_response(status_code=200, content=json.dumps({"value": []}).encode())
    mock_get = mocker.patch.object(client.session, "get", return_value=listing_resp)

    client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
        version_type=version_type,
    )

    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["recursionLevel"] == "OneLevel"
    assert sent_params["versionDescriptor.versionType"] == expected_version_type


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
