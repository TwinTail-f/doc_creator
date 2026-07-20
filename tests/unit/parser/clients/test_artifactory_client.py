"""
Юнит-тесты для autodoc/parser/clients/artifactory_client.py.

Весь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.
"""

from unittest.mock import MagicMock

import pytest
import requests

from autodoc.parser.clients.artifactory_client import ArtifactoryClient


def _make_artifactory_client(parser_config) -> ArtifactoryClient:
    """
    Создаёт ArtifactoryClient из минимальной корректной конфигурации парсера.

    Args:
        parser_config: Валидированная конфигурация парсера (фикстура).

    Returns:
        Готовый к использованию экземпляр ArtifactoryClient.
    """
    return ArtifactoryClient(parser_config)


@pytest.mark.infrastructure
def test_artifactory_client_head_returns_response(mocker, parser_config) -> None:
    """ArtifactoryClient.head выполняет HEAD-запрос с allow_redirects=True и возвращает HTTP-ответ."""
    client = _make_artifactory_client(parser_config)
    mock_resp = MagicMock(spec=requests.Response)
    mock_head = mocker.patch.object(client.session, "head", return_value=mock_resp)

    url = "https://art.example.com/artifactory/conan2/openssl"
    response = client.head(url)

    assert response is mock_resp
    mock_head.assert_called_once_with(url, allow_redirects=True)
