"""
Pydantic-схемы для валидации конфигурационных файлов проекта.
Совместимо с Pydantic v2.
"""

from typing import Any, Literal
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
        description='Ветка или тег в репозитории (например "develop" или "0")',
    )
    platform_ref_type: Literal["branch", "tag", "commit"] = Field(
        default="branch",
        description='Тип версии: "branch" (по умолчанию), "tag" или "commit"',
    )
    username: str = Field(
        ...,
        description="Имя пользователя TFS / Artifactory (используется в conan remote login и config install)",
    )
    tfs_token: str = Field(
        ...,
        description="Personal Access Token для TFS",
    )
    artifactory_token: str | None = Field(
        default=None,
        validate_default=True,
        description="PAT-токен Artifactory",
    )
    tfs_dep_components_url: str = Field(
        ...,
        description="Базовый URL проекта DEP_Components в TFS",
    )
    manifests_remotes_path: str = Field(
        ...,
        description="Путь к директории с манифестами в TFS",
    )
    conan_config_url: str = Field(
        ..., description="URL zip-архива конфигурации Conan в Artifactory"
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
    publish_batch_size: int = Field(
        default=10,
        ge=1,
        le=200,
        description=(
            "Количество страниц паспортов, публикуемых в одном пакете. "
            "Уменьшите при перегрузках сервера Confluence."
        ),
    )
    publish_batch_delay_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=60.0,
        description=(
            "Задержка в секундах между пакетами при публикации паспортов. "
            "0 — без задержки."
        ),
    )
    target_release_version: str = Field(
        default="Platform 2.2",
        description='Подпись текущего релиза (например "Platform 2.2"). '
        "Используется в заголовке паспортов и метке вкладки релиза.",
    )
    preserve_legacy_platforms: list[str] = Field(
        default_factory=list,
        description="Список имён старых платформ, контент которых нужно сохранить",
    )
