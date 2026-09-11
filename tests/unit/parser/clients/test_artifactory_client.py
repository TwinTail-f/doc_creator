"""
Юнит-тесты для autodoc/parser/clients/artifactory_client.py.

Весь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.
"""

from unittest.mock import MagicMock

import pytest
import requests

from autodoc.parser.clients.artifactory_client import ArtifactoryClient


@pytest.fixture
def artifactory_client(parser_config) -> ArtifactoryClient:
    """Готовый к использованию ArtifactoryClient, созданный из parser_config."""
    return ArtifactoryClient(parser_config)


@pytest.mark.infrastructure
def test_artifactory_client_check_url_returns_response(mocker, artifactory_client) -> None:
    """
    ArtifactoryClient.check_url делегирует HEAD-запрос сессии с allow_redirects=True
    и возвращает её ответ без изменений (URL при этом не валидируется)."""
    client = artifactory_client
    mock_resp = MagicMock(spec=requests.Response)
    mock_head = mocker.patch.object(client.session, "head", return_value=mock_resp)

    url = "https://art.example.com/artifactory/conan2/openssl"
    response = client.check_url(url)

    assert response is mock_resp
    mock_head.assert_called_once_with(url, allow_redirects=True)
