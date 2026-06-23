"""
Схема конфигурации Confluence.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    verify_ssl: bool = Field(
        default=True,
        description="Проверять SSL-сертификаты",
    )

    release_docs_root_parent_id: str | None = Field(
        default=None,
        description=(
            "ID корневой родительской страницы релизной документации. "
            "Используется как запасной вариант, если release_docs_root_parent_name не задан."
        ),
    )
    release_docs_root_parent_name: str | None = Field(
        default=None,
        description=(
            "Название корневой родительской страницы релизной документации. "
            "Если задано — используется вместо release_docs_root_parent_id "
            "(приоритет: release_docs_root_parent_name > release_docs_root_parent_id)."
        ),
    )
    release_docs_page_title: str | None = Field(
        default="Сборки компонентов Платформы",
        description="Заголовок корневой страницы релизной документации.",
    )
    profile_docs_page_title: str | None = Field(
        default=None,
        description="Заголовок страницы профиль-центричной документации.",
    )
    passports_root_parent_id: str | None = Field(
        default=None,
        description="ID родительской страницы для дерева паспортов",
    )
    passports_root_parent_name: str | None = Field(
        default=None,
        description=(
            "Название корневой страницы для дерева паспортов. "
            "Если задано — используется вместо passports_root_parent_id "
            "(приоритет: passports_root_parent_name > passports_root_parent_id)."
        ),
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

    @field_validator("url")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        """Проверяет непустоту URL и убирает завершающий слеш."""
        if not v or not v.strip():
            raise ValueError("url не может быть пустым")
        return v.rstrip("/")
