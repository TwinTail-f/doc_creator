"""
Юнит-тесты для autodoc/parser/clients/tfs_client.py.
"""

from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from autodoc.exceptions import NetworkError
from autodoc.parser.clients.tfs_client import TFSClient
from autodoc.parser.clients.tfs_client_enums import RecursionLevel, VersionType

TFS_URL: str = "https://tfs.example.com"
BRANCH: str = "develop"
REMOTE_PATH: str = "/platform/manifests"


@pytest.fixture
def tfs_client(parser_config) -> TFSClient:
    """Готовый к использованию TFSClient, созданный из parser_config."""
    return TFSClient(parser_config)


def _query_params(request: requests.PreparedRequest) -> dict[str, str]:
    """Возвращает query-параметры фактически отправленного запроса в виде плоского словаря."""
    parsed = urlparse(request.url)
    return {key: values[0] for key, values in parse_qs(parsed.query).items()}


@pytest.mark.infrastructure
@responses.activate
def test_tfs_client_get_file_content_returns_response(tfs_client: TFSClient) -> None:
    """TFSClient.get_file_content возвращает HTTP-ответ сессии без изменений."""
    responses.add(responses.GET, TFS_URL, body=b"hello", status=200)

    response = tfs_client.get_file_content(TFS_URL, "/path/file.json", BRANCH)

    assert response.status_code == 200
    assert response.content == b"hello"


@pytest.mark.infrastructure
@responses.activate
def test_tfs_client_get_file_content_raises_network_error_on_failure(tfs_client: TFSClient) -> None:
    """TFSClient.get_file_content оборачивает RequestException в NetworkError."""
    responses.add(responses.GET, TFS_URL, body=requests.RequestException("timeout"))

    with pytest.raises(NetworkError):
        tfs_client.get_file_content(TFS_URL, "/path/file.json", BRANCH)


@pytest.mark.contract
@pytest.mark.parametrize(
    "version_type, expected",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
@responses.activate
def test_tfs_client_get_file_content_sends_version_type_in_request(
    tfs_client: TFSClient, version_type: VersionType, expected: str
) -> None:
    """get_file_content передаёт versionDescriptor.versionType в параметрах запроса согласно переданному VersionType."""
    responses.add(responses.GET, TFS_URL, body=b"data", status=200)

    tfs_client.get_file_content(TFS_URL, "/path/file.json", BRANCH, version_type=version_type)

    sent_params = _query_params(responses.calls[0].request)
    assert sent_params["versionDescriptor.versionType"] == expected


@pytest.mark.infrastructure
@responses.activate
def test_tfs_client_get_items_returns_item_list(tfs_client: TFSClient) -> None:
    """TFSClient.get_items возвращает список, извлечённый из ключа 'value'."""
    items = [{"path": "/a.properties"}, {"path": "/b.properties"}]
    responses.add(responses.GET, TFS_URL, json={"value": items}, status=200)

    result = tfs_client.get_items(TFS_URL, BRANCH)

    assert result == items


@pytest.mark.infrastructure
@responses.activate
def test_tfs_client_get_items_raises_network_error_on_http_error(tfs_client: TFSClient) -> None:
    """TFSClient.get_items вызывает NetworkError, когда сессия бросает RequestException."""
    responses.add(responses.GET, TFS_URL, body=requests.RequestException("server error"))

    with pytest.raises(NetworkError):
        tfs_client.get_items(TFS_URL, BRANCH)


@pytest.mark.contract
@pytest.mark.parametrize(
    "version_type, expected",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
@responses.activate
def test_tfs_client_get_items_sends_version_type_in_request(
    tfs_client: TFSClient, version_type: VersionType, expected: str
) -> None:
    """get_items передаёт versionDescriptor.versionType в параметрах запроса согласно переданному VersionType."""
    responses.add(responses.GET, TFS_URL, json={"value": []}, status=200)

    tfs_client.get_items(TFS_URL, BRANCH, version_type=version_type)

    sent_params = _query_params(responses.calls[0].request)
    assert sent_params["versionDescriptor.versionType"] == expected


@pytest.mark.contract
@pytest.mark.parametrize(
    "recursion, expected",
    [
        pytest.param(RecursionLevel.ONE_LEVEL, "OneLevel", id="one-level"),
        pytest.param(RecursionLevel.FULL, "Full", id="full"),
    ],
)
@responses.activate
def test_tfs_client_get_items_sends_recursion_level_in_request(
    tfs_client: TFSClient, recursion: RecursionLevel, expected: str
) -> None:
    """get_items передаёт recursionLevel в параметрах запроса согласно переданному RecursionLevel."""
    responses.add(responses.GET, TFS_URL, json={"value": []}, status=200)

    tfs_client.get_items(TFS_URL, BRANCH, recursion=recursion)

    sent_params = _query_params(responses.calls[0].request)
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
@responses.activate
def test_tfs_client_download_properties_filters_items_before_downloading(
    tfs_client: TFSClient,
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
    responses.add(responses.GET, TFS_URL, json={"value": listing_items}, status=200)
    responses.add(responses.GET, TFS_URL, body=downloaded_content.encode(), status=200)

    tfs_client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
    )

    assert (tmp_path / downloaded_name).read_text(encoding="utf-8") == downloaded_content
    assert not (tmp_path / skipped_name).exists()
    assert len(responses.calls) == 2, "ожидался один запрос листинга и ровно одно скачивание файла"


@pytest.mark.contract
@pytest.mark.parametrize(
    "version_type, expected_version_type",
    [
        pytest.param(VersionType.BRANCH, "branch", id="branch"),
        pytest.param(VersionType.TAG, "tag", id="tag"),
        pytest.param(VersionType.COMMIT, "commit", id="commit"),
    ],
)
@responses.activate
def test_tfs_client_download_properties_lists_with_correct_request_params(
    tfs_client: TFSClient, tmp_path, version_type: VersionType, expected_version_type: str
) -> None:
    """
    download_properties запрашивает листинг файлов с recursionLevel=OneLevel (фиксировано)
    и versionDescriptor.versionType согласно переданному version_type.
    """
    responses.add(responses.GET, TFS_URL, json={"value": []}, status=200)

    tfs_client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
        version_type=version_type,
    )

    sent_params = _query_params(responses.calls[0].request)
    assert sent_params["recursionLevel"] == "OneLevel"
    assert sent_params["versionDescriptor.versionType"] == expected_version_type


@pytest.mark.infrastructure
@responses.activate
def test_tfs_client_download_properties_raises_on_listing_failure(
    tfs_client: TFSClient, tmp_path
) -> None:
    """download_properties пробрасывает NetworkError при сбое запроса листинга."""
    responses.add(responses.GET, TFS_URL, body=requests.RequestException("connection refused"))

    with pytest.raises(NetworkError):
        tfs_client.download_properties(
            items_url=TFS_URL,
            remote_path=REMOTE_PATH,
            branch=BRANCH,
            output_dir=str(tmp_path),
        )


@pytest.mark.infrastructure
@responses.activate
def test_tfs_client_download_properties_continues_after_single_file_failure(
    tfs_client: TFSClient, tmp_path
) -> None:
    """Сбой скачивания одного .properties-файла не прерывает загрузку остальных файлов из списка."""
    listing_items = [
        {"path": "/platform/broken.properties", "isFolder": False},
        {"path": "/platform/ok.properties", "isFolder": False},
    ]
    responses.add(responses.GET, TFS_URL, json={"value": listing_items}, status=200)
    responses.add(responses.GET, TFS_URL, body=requests.RequestException("boom"))
    responses.add(responses.GET, TFS_URL, body=b"name=ok", status=200)

    tfs_client.download_properties(
        items_url=TFS_URL,
        remote_path=REMOTE_PATH,
        branch=BRANCH,
        output_dir=str(tmp_path),
    )

    assert not (tmp_path / "broken.properties").exists()
    assert (tmp_path / "ok.properties").read_text(encoding="utf-8") == "name=ok"
