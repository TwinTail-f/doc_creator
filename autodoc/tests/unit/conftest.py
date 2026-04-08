"""
Общие фикстуры и константы для unit-тестов.
"""

import pytest

from autodoc.config.schemas import ParserConfigSchema

# Словарь минимально-валидной конфигурации парсера.
# Используется в test_config.py для записи в файлы и в фикстуре minimal_config.
VALID_PARSER_CONFIG: dict = {
    "platform_version": "2.0",
    "platform_branch_name": "develop",
    "tfs_username": "robot",
    "tfs_token": "secret-pat",
    "tfs_dep_components_url": "https://tfs.example.com/DEP_Components",
    "manifests_remotes_path": "/remotes/manifests",
    "artifactory_token": "art-token",
}


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
        artifactory_token="art-token",
        max_retries=2,
        retry_backoff_factor=1.5,
    )
