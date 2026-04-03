"""
Общие фикстуры для unit-тестов.
"""
import pytest

from autodoc.config.schemas import ParserConfigSchema
from autodoc.infrastructure.singleton import Singleton
from autodoc.parser.clients.artifactory_client import ArtifactoryClient
from autodoc.parser.clients.tfs_client import TFSClient


@pytest.fixture
def minimal_config() -> ParserConfigSchema:
    """Минимальная валидная конфигурация парсера для тестов."""
    return ParserConfigSchema(
        platform_version="2.0",
        platform_branch_name="develop",
        tfs_username="robot",
        tfs_token="secret-token",
        tfs_dep_components_url="https://tfs.example.com/DEP_Components",
        manifests_remotes_path="/remotes/manifests",
        tfs_request_timeout=10,
        max_retries=2,
        retry_backoff_factor=1.5,
    )


@pytest.fixture(autouse=True)
def reset_all_singletons():
    """Сбрасывает все синглтоны до и после каждого теста."""
    TFSClient.reset()
    ArtifactoryClient.reset()
    yield
    TFSClient.reset()
    ArtifactoryClient.reset()
