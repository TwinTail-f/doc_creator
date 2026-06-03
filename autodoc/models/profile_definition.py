"""
Модель определения профиля сборки.

ProfileDefinition — настройки и Docker-образ для конкретного профиля,
дедублированные на уровне ParsedResult.
"""

from typing import Any

from pydantic import BaseModel, Field


class ProfileDefinition(BaseModel):
    """Настройки и Docker-образ для конкретного профиля, дедублированные на уровне ParsedResult."""

    profile_name: str = Field(..., description="Имя профиля сборки (уникальный ключ)")
    conan_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Настройки Conan для данного профиля",
    )
    docker_image: str = Field(
        default="",
        description="URL Docker-образа для данного профиля",
    )
