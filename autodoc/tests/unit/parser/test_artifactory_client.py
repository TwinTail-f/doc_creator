"""
Unit-тесты для ArtifactoryClient.

Покрывают:
- инициализацию (передача credentials, отключение SSL)
- метод head() и подавление InsecureRequestWarning
"""

import pytest
import requests
import urllib3
from unittest.mock import MagicMock, patch

from autodoc.config.schemas import ParserConfigSchema
from autodoc.parser.clients.artifactory_client import ArtifactoryClient, _HEAD_TIMEOUT

_ART_SESSION_PATH = "autodoc.parser.clients.artifactory_client.create_retryable_session"


# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------


def _make_mock_session() -> MagicMock:
    session = MagicMock()
    session.verify = True  # будет переопределено в __init__
    return session


# ---------------------------------------------------------------------------
# Инициализация
# ---------------------------------------------------------------------------


class TestArtifactoryClientInit:
    """Тесты инициализации ArtifactoryClient."""

    def test_session_created_with_artifactory_credentials(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """create_retryable_session вызывается с артифактори-кредами из конфига."""
        config_with_creds = minimal_config.model_copy(
            update={
                "artifactory_username": "art_user",
                "artifactory_password": "art_pass",
            }
        )
        mock_session = _make_mock_session()

        with patch(_ART_SESSION_PATH, return_value=mock_session) as mock_factory:
            ArtifactoryClient(config_with_creds)

        mock_factory.assert_called_once_with(
            username="art_user",
            token="art_pass",
            max_retries=1,
            timeout=_HEAD_TIMEOUT,
        )

    def test_ssl_verification_disabled(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """session.verify устанавливается в False при инициализации."""
        mock_session = _make_mock_session()
        with patch(_ART_SESSION_PATH, return_value=mock_session):
            ArtifactoryClient(minimal_config)

        assert mock_session.verify is False

    def test_created_without_credentials_does_not_raise(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """ArtifactoryClient создаётся без ошибок даже при пустых кредах."""
        config_no_creds = minimal_config.model_copy(
            update={"artifactory_username": "", "artifactory_password": ""}
        )
        mock_session = _make_mock_session()
        with patch(_ART_SESSION_PATH, return_value=mock_session):
            client = ArtifactoryClient(config_no_creds)

        assert client.session is mock_session

    def test_each_call_creates_independent_instance(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """Каждый вызов ArtifactoryClient(config) возвращает новый независимый экземпляр."""
        with patch(_ART_SESSION_PATH, return_value=_make_mock_session()):
            first = ArtifactoryClient(minimal_config)
            second = ArtifactoryClient(minimal_config)

        assert first is not second

    def test_tfs_and_artifactory_are_independent(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """TFSClient и ArtifactoryClient — полностью независимые объекты."""
        from autodoc.parser.clients.tfs_client import TFSClient

        with patch(
            "autodoc.parser.clients.tfs_client.create_retryable_session",
            return_value=_make_mock_session(),
        ):
            tfs = TFSClient(minimal_config)

        with patch(_ART_SESSION_PATH, return_value=_make_mock_session()):
            art = ArtifactoryClient(minimal_config)

        assert tfs is not art


# ---------------------------------------------------------------------------
# head()
# ---------------------------------------------------------------------------


class TestArtifactoryClientHead:
    """Тесты метода ArtifactoryClient.head."""

    @pytest.fixture
    def client(self, minimal_config: ParserConfigSchema) -> ArtifactoryClient:
        mock_session = _make_mock_session()
        with patch(_ART_SESSION_PATH, return_value=mock_session):
            return ArtifactoryClient(minimal_config)

    def test_returns_response_from_session(self, client: ArtifactoryClient) -> None:
        """head() возвращает ответ от session.head."""
        mock_response = MagicMock(spec=requests.Response)
        client.session.head.return_value = mock_response

        result = client.head("https://artifactory.example.com/pkg/1.0.0")

        assert result is mock_response

    def test_passes_url_and_params_to_session(self, client: ArtifactoryClient) -> None:
        """head() вызывает session.head с allow_redirects=True и правильным таймаутом."""
        client.session.head.return_value = MagicMock(spec=requests.Response)

        client.head("https://artifactory.example.com/pkg/1.0.0")

        client.session.head.assert_called_once_with(
            "https://artifactory.example.com/pkg/1.0.0",
            allow_redirects=True,
            timeout=_HEAD_TIMEOUT,
        )

    def test_suppresses_insecure_request_warning(
        self, client: ArtifactoryClient
    ) -> None:
        """head() выполняется без InsecureRequestWarning даже при verify=False."""
        client.session.head.return_value = MagicMock(spec=requests.Response)

        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.head("https://artifactory.example.com/pkg")

        insecure_warnings = [
            w
            for w in caught
            if issubclass(w.category, urllib3.exceptions.InsecureRequestWarning)
        ]
        assert len(insecure_warnings) == 0
