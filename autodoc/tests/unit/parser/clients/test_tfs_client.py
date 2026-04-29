"""
Unit tests for autodoc/parser/clients/tfs_client.py.

All HTTP I/O is mocked — no real network calls are made.
"""

import json
from unittest.mock import MagicMock

import pytest
import requests

from autodoc.exceptions import NetworkError
from autodoc.parser.clients.tfs_client import TFSClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TFS_URL: str = "https://tfs.example.com"
BRANCH: str = "develop"
REMOTE_PATH: str = "/platform/manifests"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int = 200, content: bytes = b"") -> MagicMock:
    """Return a mock requests.Response with the given status code and content."""
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
    """Instantiate TFSClient from a minimal valid parser config."""
    return TFSClient(parser_config)


# ---------------------------------------------------------------------------
# 1.1 — get_file_content: successful response is returned
# ---------------------------------------------------------------------------


def test_tfs_client_get_file_content_returns_response(mocker, parser_config) -> None:
    """TFSClient.get_file_content returns the HTTP response on success."""
    client = _make_tfs_client(parser_config)
    mock_resp = _make_response(status_code=200, content=b"hello")
    mocker.patch.object(client.session, "get", return_value=mock_resp)

    response = client.get_file_content(TFS_URL, "/path/file.json", BRANCH)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 1.2 — get_file_content: network failure raises NetworkError
# ---------------------------------------------------------------------------


def test_tfs_client_get_file_content_raises_network_error_on_failure(
    mocker, parser_config
) -> None:
    """TFSClient.get_file_content wraps RequestException into NetworkError."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(
        client.session, "get", side_effect=requests.RequestException("timeout")
    )

    with pytest.raises(NetworkError):
        client.get_file_content(TFS_URL, "/path/file.json", BRANCH)


# ---------------------------------------------------------------------------
# 1.3 — get_items: parses 'value' list from JSON response
# ---------------------------------------------------------------------------


def test_tfs_client_get_items_returns_item_list(mocker, parser_config) -> None:
    """TFSClient.get_items returns the list extracted from the 'value' key."""
    items = [{"path": "/a.properties"}, {"path": "/b.properties"}]
    mock_resp = _make_response(
        status_code=200, content=json.dumps({"value": items}).encode()
    )
    client = _make_tfs_client(parser_config)
    mocker.patch.object(client.session, "get", return_value=mock_resp)

    result = client.get_items(TFS_URL, BRANCH)

    assert len(result) == 2


# ---------------------------------------------------------------------------
# 1.4 — get_items: HTTP error raises NetworkError
# ---------------------------------------------------------------------------


def test_tfs_client_get_items_raises_network_error_on_http_error(
    mocker, parser_config
) -> None:
    """TFSClient.get_items raises NetworkError when the session raises RequestException."""
    client = _make_tfs_client(parser_config)
    mocker.patch.object(
        client.session, "get", side_effect=requests.RequestException("server error")
    )

    with pytest.raises(NetworkError):
        client.get_items(TFS_URL, BRANCH)


# ---------------------------------------------------------------------------
# 1.5 — download_properties: downloads .properties files, skips others
# ---------------------------------------------------------------------------


def test_tfs_client_download_properties_downloads_files(
    mocker, parser_config, tmp_path
) -> None:
    """
    download_properties writes .properties files to tmp_path and skips other extensions.

    The listing response provides two items; only the .properties one is written.
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


# ---------------------------------------------------------------------------
# 1.6 — download_properties: listing failure propagates NetworkError
# ---------------------------------------------------------------------------


def test_tfs_client_download_properties_raises_on_listing_failure(
    mocker, parser_config, tmp_path
) -> None:
    """download_properties propagates NetworkError when the listing request fails."""
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
