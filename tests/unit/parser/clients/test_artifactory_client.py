"""
Юнит-тесты для autodoc/parser/clients/artifactory_client.py.

Весь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.
"""

from unittest.mock import MagicMock

import pytest
import requests

from autodoc.parser.clients.artifactory_client import ArtifactoryClient

_EXAMPLE_URL: str = "https://art.example.com/artifactory/conan2/openssl"


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
    """ArtifactoryClient.head возвращает HTTP-ответ при успешном HEAD-запросе."""
    client = _make_artifactory_client(parser_config)
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 200
    mocker.patch.object(client.session, "head", return_value=mock_resp)

    response = client.head(_EXAMPLE_URL)

    assert response.status_code == 200
