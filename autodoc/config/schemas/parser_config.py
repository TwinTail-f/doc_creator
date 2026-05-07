"""
Схема конфигурации парсера компонентов.
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

    @field_validator("tfs_token")
    @classmethod
    def tfs_token_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("tfs_token не может быть пустой строкой")
        return v

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
