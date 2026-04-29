"""
Unit tests for autodoc/parser/clients/artifactory_client.py.

All HTTP I/O is mocked — no real network calls are made.
"""

from unittest.mock import MagicMock

import pytest
import requests

from autodoc.parser.clients.artifactory_client import ArtifactoryClient
from autodoc.parser.clients.protocols import IArtifactoryClient, ITFSClient
from autodoc.parser.clients.tfs_client import TFSClient

_EXAMPLE_URL: str = "https://art.example.com/artifactory/conan2/openssl"


def _make_artifactory_client(parser_config) -> ArtifactoryClient:
    """Instantiate ArtifactoryClient from a minimal valid parser config."""
    return ArtifactoryClient(parser_config)


# ---------------------------------------------------------------------------
# 2.1 — head: returns response on success
# ---------------------------------------------------------------------------


def test_artifactory_client_head_returns_response(mocker, parser_config) -> None:
    """ArtifactoryClient.head returns the HTTP response on a successful HEAD request."""
    client = _make_artifactory_client(parser_config)
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 200
    mocker.patch.object(client.session, "head", return_value=mock_resp)

    response = client.head(_EXAMPLE_URL)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 2.2 — head: SSL verification is disabled at the session level
# ---------------------------------------------------------------------------


def test_artifactory_client_head_disables_ssl_verification(
    parser_config,
) -> None:
    """ArtifactoryClient sets verify=False on the session, disabling SSL verification."""
    client = _make_artifactory_client(parser_config)

    assert client.session.verify is False


# ---------------------------------------------------------------------------
# 2.3 — Protocol conformance: ArtifactoryClient satisfies IArtifactoryClient
# ---------------------------------------------------------------------------


def test_artifactory_client_satisfies_protocol(parser_config) -> None:
    """ArtifactoryClient structurally satisfies the IArtifactoryClient Protocol."""
    client = ArtifactoryClient.__new__(ArtifactoryClient)

    assert isinstance(client, IArtifactoryClient)


# ---------------------------------------------------------------------------
# 2.4 — Protocol conformance: TFSClient satisfies ITFSClient
# ---------------------------------------------------------------------------


def test_tfs_client_satisfies_protocol(parser_config) -> None:
    """TFSClient structurally satisfies the ITFSClient Protocol."""
    client = TFSClient.__new__(TFSClient)

    assert isinstance(client, ITFSClient)
