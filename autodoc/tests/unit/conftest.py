"""
Общие фикстуры и константы для unit-тестов.

Единственный источник истины для конфигураций в тестах.
Все тестовые файлы импортируют константы отсюда или получают
готовые объекты через фикстуры pytest.
"""

import pytest

from autodoc.config.schemas import ConfluenceConfigSchema, ParserConfigSchema

# ---------------------------------------------------------------------------
# Данные конфигурации парсера (минимально-валидный набор полей)
# ---------------------------------------------------------------------------

VALID_PARSER_CONFIG: dict = {
    "platform_version": "2.0",
    "platform_branch_name": "develop",
    "tfs_username": "robot",
    "tfs_token": "secret-pat",
    "tfs_dep_components_url": "https://tfs.example.com/DEP_Components",
    "manifests_remotes_path": "/remotes/manifests",
    "artifactory_token": "art-token",
    "conan_config_url": "https://artifactory.example.com/conan-config.zip",
}

# ---------------------------------------------------------------------------
# Данные конфигурации Confluence (минимально-валидный набор полей)
# ---------------------------------------------------------------------------

VALID_CONFLUENCE_CONFIG: dict = {
    "url": "https://confluence.example.com",
    "token": "test-pat-token",
    "space": "PROJ",
    "confluence_request_timeout": 30,
    "verify_ssl": True,
}

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_config() -> ParserConfigSchema:
    """Минимальная валидная конфигурация парсера для тестов."""
    return ParserConfigSchema(**VALID_PARSER_CONFIG)


@pytest.fixture
def minimal_confluence_config() -> ConfluenceConfigSchema:
    """Минимальная валидная конфигурация Confluence для тестов."""
    return ConfluenceConfigSchema(**VALID_CONFLUENCE_CONFIG)
