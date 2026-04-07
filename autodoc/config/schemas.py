"""
Pydantic-схемы для валидации конфигурационных файлов проекта.
Совместимо с Pydantic v2.
"""
import os

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParserConfigSchema(BaseModel):
    """Схема валидации ``parser_config.json`` / ``parser_config.yaml``."""

    model_config = ConfigDict(extra="allow")

    # Обязательные поля
    platform_version: str = Field(
        ...,
        description='Версия платформы (например "2.0")',
    )
    platform_branch_name: str = Field(
        ...,
        description='Ветка в репозитории (например "develop")',
    )
    tfs_token: str = Field(
        ...,
        description="Personal Access Token для TFS",
    )
    tfs_dep_components_url: str = Field(
        ...,
        description="Базовый URL проекта DEP_Components в TFS",
    )
    manifests_remotes_path: str = Field(
        ...,
        description="Путь к директории с манифестами в TFS",
    )

    # tfs_username опционален: Azure DevOps принимает любое (в т. ч. пустое) значение при PAT-auth
    tfs_username: str = Field(
        default="",
        description="Имя пользователя TFS (опционально при PAT-аутентификации)",
    )

    # Опциональные поля
    artifactory_components_conan2_url: str = Field(
        default="",
        description="URL Artifactory для Conan 2 пакетов",
    )
    profiles_urls: list[str] = Field(
        default_factory=list,
        description="Список URL на YAML-файлы профилей сборки",
    )
    excluded_components: list[str] = Field(
        default_factory=list,
        description="Список компонентов для исключения из обработки",
    )

    # Credentials Artifactory — из конфига с fallback на env-переменные.
    artifactory_username: str | None = Field(
        default=None,
        description="Пользователь Artifactory (из env GET_USR если не задан явно)",
    )
    artifactory_password: str | None = Field(
        default=None,
        description="Пароль Artifactory (из env GET_PWD если не задан явно)",
    )

    # Тайм-ауты
    tfs_request_timeout: int = Field(
        default=15,
        ge=1,
        le=120,
        description="Тайм-аут HTTP-запросов к TFS (секунды)",
    )
    conan_command_timeout: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="Тайм-аут выполнения команд Conan (секунды)",
    )

    # Retry-логика
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Максимальное количество retry-попыток для сетевых операций",
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Множитель для exponential backoff (1 с, затем 2, 4, 8…)",
    )

    _ENV_MAP: dict[str, str] = {
        "artifactory_username": "GET_USR",
        "artifactory_password": "GET_PWD",
    }

    @field_validator("artifactory_username", "artifactory_password", mode="before")
    @classmethod
    def fill_artifactory_credentials_from_env(
        cls, v: str | None, info: Any
    ) -> str:  # type: ignore[override]
        """
        Заполняет Artifactory-credentials из env GET_USR / GET_PWD если не заданы явно.

        Raises:
            ValueError: Если ни конфигурация, ни переменная окружения не содержат значение.
        """
        if v:
            return v
        env_map = {"artifactory_username": "GET_USR", "artifactory_password": "GET_PWD"}
        env_key = env_map[info.field_name]
        env_val = os.getenv(env_key, "")
        if not env_val:
            raise ValueError(
                f"Поле {info.field_name!r} не задано в конфигурации "
                f"и переменная окружения {env_key!r} не установлена. "
                "Укажите credentials явно или задайте соответствующую переменную окружения."
            )
        return env_val


class ConfluenceConfigSchema(BaseModel):
    """Схема валидации ``confluence_config.json`` / ``confluence_config.yaml``."""

    model_config = ConfigDict(extra="allow")

    url: str = Field(
        ...,
        description="Базовый URL Confluence",
    )
    token: str = Field(
        ...,
        description="Atlassian API-токен",
    )
    space: str = Field(
        ...,
        description="Ключ Space в Confluence",
    )

    username: str | None = Field(
        default=None,
        description="Имя пользователя (legacy-аутентификация, не используется при PAT)",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Проверять SSL-сертификаты",
    )

    parent_id: str | None = Field(
        default=None,
        description="ID родительской страницы",
    )
    page_title: str | None = Field(
        default="Сборки компонентов Платформы",
        description="Заголовок главной страницы",
    )
    passports_root_parent_id: str | None = Field(
        default=None,
        description="ID родительской страницы для дерева паспортов",
    )

    confluence_request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Тайм-аут HTTP-запросов к Confluence (секунды)",
    )
    target_platform_version: str = Field(
        default="Platform 2.2",
        description='Имя текущей платформы (например "Platform 2.2")',
    )
    preserve_legacy_platforms: list[str] = Field(
        default_factory=list,
        description="Список имён старых платформ, контент которых нужно сохранить",
    )
