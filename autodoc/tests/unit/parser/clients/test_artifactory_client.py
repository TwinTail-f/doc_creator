"""
Юнит-тесты для autodoc/parser/clients/artifactory_client.py.

Весь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.
"""

from unittest.mock import MagicMock

import pytest
import requests

from autodoc.parser.clients.artifactory_client import ArtifactoryClient
from autodoc.parser.clients.protocols import IArtifactoryClient, ITFSClient
from autodoc.parser.clients.tfs_client import TFSClient

_EXAMPLE_URL: str = "https://art.example.com/artifactory/conan2/openssl"


def _make_artifactory_client(parser_config) -> ArtifactoryClient:
    """Создаёт ArtifactoryClient из минимальной корректной конфигурации парсера."""
    return ArtifactoryClient(parser_config)


# ---------------------------------------------------------------------------
# head: возвращает ответ при успехе
# ---------------------------------------------------------------------------


def test_artifactory_client_head_returns_response(mocker, parser_config) -> None:
    """ArtifactoryClient.head возвращает HTTP-ответ при успешном HEAD-запросе."""
    client = _make_artifactory_client(parser_config)
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 200
    mocker.patch.object(client.session, "head", return_value=mock_resp)

    response = client.head(_EXAMPLE_URL)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# head: проверка SSL отключена на уровне сессии
# ---------------------------------------------------------------------------


def test_artifactory_client_head_disables_ssl_verification(
    parser_config,
) -> None:
    """ArtifactoryClient устанавливает verify=False для сессии, отключая проверку SSL."""
    client = _make_artifactory_client(parser_config)

    assert client.session.verify is False


# ---------------------------------------------------------------------------
# Соответствие протоколу: ArtifactoryClient удовлетворяет IArtifactoryClient
# ---------------------------------------------------------------------------


def test_artifactory_client_satisfies_protocol(parser_config) -> None:
    """ArtifactoryClient структурно удовлетворяет протоколу IArtifactoryClient."""
    client = ArtifactoryClient.__new__(ArtifactoryClient)

    assert isinstance(client, IArtifactoryClient)


# ---------------------------------------------------------------------------
# Соответствие протоколу: TFSClient удовлетворяет ITFSClient
# ---------------------------------------------------------------------------


def test_tfs_client_satisfies_protocol(parser_config) -> None:
    """TFSClient структурно удовлетворяет протоколу ITFSClient."""
    client = TFSClient.__new__(TFSClient)

    assert isinstance(client, ITFSClient)
