"""
Тесты синглтон-поведения TFSClient и ArtifactoryClient.

Проверяют: создание, идентичность экземпляров, shutdown и reset.
"""
import pytest
from unittest.mock import MagicMock, patch

from autodoc.config.schemas import ParserConfigSchema
from autodoc.infrastructure.singleton import Singleton
from autodoc.parser.tfs_client import TFSClient
from autodoc.parser.artifactory_client import ArtifactoryClient

MINIMAL_CONFIG = ParserConfigSchema(
    platform_version='2.0',
    platform_branch_name='develop',
    tfs_username='robot',
    tfs_token='secret',
    tfs_dep_components_url='https://tfs.example.com/DEP',
    manifests_remotes_path='/remotes/manifests',
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Сбрасывает реестр синглтонов до и после каждого теста."""
    TFSClient.reset()
    ArtifactoryClient.reset()
    yield
    TFSClient.reset()
    ArtifactoryClient.reset()


class TestSingletonMetaclass:
    """Тесты поведения метакласса Singleton."""

    def test_same_instance_on_repeated_calls(self) -> None:
        """Повторный вызов возвращает тот же экземпляр."""
        with patch('autodoc.parser.tfs_client.create_retryable_session', return_value=MagicMock()):
            first = TFSClient(MINIMAL_CONFIG)
            second = TFSClient(MINIMAL_CONFIG)
        assert first is second

    def test_reset_allows_new_instance(self) -> None:
        """После reset() создаётся новый экземпляр."""
        with patch('autodoc.parser.tfs_client.create_retryable_session', return_value=MagicMock()):
            first = TFSClient(MINIMAL_CONFIG)
            TFSClient.reset()
            second = TFSClient(MINIMAL_CONFIG)
        assert first is not second

    def test_singleton_instances_are_class_local(self) -> None:
        """TFSClient и ArtifactoryClient хранятся раздельно в реестре Singleton."""
        mock_session = MagicMock()
        with patch('autodoc.parser.tfs_client.create_retryable_session', return_value=mock_session):
            tfs = TFSClient(MINIMAL_CONFIG)
        with patch(
            'autodoc.parser.artifactory_client.create_retryable_session',
            return_value=mock_session,
        ):
            art = ArtifactoryClient(MINIMAL_CONFIG)

        assert TFSClient in Singleton._instances
        assert ArtifactoryClient in Singleton._instances
        assert tfs is not art


class TestTFSClientSingleton:
    """Тесты жизненного цикла синглтона TFSClient."""

    def test_shutdown_closes_session_and_removes_instance(self) -> None:
        """shutdown() закрывает сессию и удаляет экземпляр из реестра."""
        mock_session = MagicMock()
        with patch('autodoc.parser.tfs_client.create_retryable_session', return_value=mock_session):
            TFSClient(MINIMAL_CONFIG)

        TFSClient.shutdown()

        mock_session.close.assert_called_once()
        assert TFSClient not in Singleton._instances

    def test_shutdown_is_idempotent(self) -> None:
        """Повторный вызов shutdown() не вызывает ошибок."""
        with patch('autodoc.parser.tfs_client.create_retryable_session', return_value=MagicMock()):
            TFSClient(MINIMAL_CONFIG)
        TFSClient.shutdown()
        TFSClient.shutdown()  # второй вызов — no-op

    def test_reset_does_not_close_session(self) -> None:
        """reset() удаляет экземпляр без закрытия сессии."""
        mock_session = MagicMock()
        with patch('autodoc.parser.tfs_client.create_retryable_session', return_value=mock_session):
            TFSClient(MINIMAL_CONFIG)

        TFSClient.reset()

        mock_session.close.assert_not_called()
        assert TFSClient not in Singleton._instances

    def test_init_raises_config_error_when_no_credentials(self) -> None:
        """ConfigError при отсутствии учётных данных."""
        from autodoc.exceptions import ConfigError
        bad_config = ParserConfigSchema(
            platform_version='2.0',
            platform_branch_name='develop',
            tfs_username='',
            tfs_token='',
            tfs_dep_components_url='https://tfs.example.com/DEP',
            manifests_remotes_path='/remotes/manifests',
        )
        with pytest.raises(ConfigError):
            TFSClient(bad_config)


class TestArtifactoryClientSingleton:
    """Тесты жизненного цикла синглтона ArtifactoryClient."""

    def test_shutdown_closes_session_and_removes_instance(self) -> None:
        """shutdown() закрывает сессию и удаляет экземпляр из реестра."""
        mock_session = MagicMock()
        with patch(
            'autodoc.parser.artifactory_client.create_retryable_session',
            return_value=mock_session,
        ):
            ArtifactoryClient(MINIMAL_CONFIG)

        ArtifactoryClient.shutdown()

        mock_session.close.assert_called_once()
        assert ArtifactoryClient not in Singleton._instances

    def test_shutdown_is_idempotent(self) -> None:
        """Повторный вызов shutdown() не вызывает ошибок."""
        with patch(
            'autodoc.parser.artifactory_client.create_retryable_session',
            return_value=MagicMock(),
        ):
            ArtifactoryClient(MINIMAL_CONFIG)
        ArtifactoryClient.shutdown()
        ArtifactoryClient.shutdown()  # второй вызов — no-op

    def test_same_instance_returned_on_repeated_calls(self) -> None:
        """Повторный вызов ArtifactoryClient(config) возвращает тот же экземпляр."""
        mock_session = MagicMock()
        with patch(
            'autodoc.parser.artifactory_client.create_retryable_session',
            return_value=mock_session,
        ):
            first = ArtifactoryClient(MINIMAL_CONFIG)
            second = ArtifactoryClient(MINIMAL_CONFIG)
        assert first is second
