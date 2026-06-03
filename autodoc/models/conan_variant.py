"""
Модели вариантов и профилей сборки Conan-пакета.

ConanVariant  — один конкретный вариант сборки (конкретный package_id).
ProfileBuild  — сборка компонента под конкретный профиль.
"""

from pydantic import BaseModel, Field


class ConanVariant(BaseModel):
    """Один конкретный вариант сборки Conan-пакета (конкретный package_id)."""

    package_id: str = Field(..., description="Идентификатор Conan-пакета")
    build_url: str = Field(default="", description="URL сборки в Artifactory")
    build_date: str = Field(default="", description="Дата сборки пакета")
    options_ref: str = Field(
        default="",
        description="Ссылка на элемент Release.total_option_sets по идентификатору",
    )


class ProfileBuild(BaseModel):
    """Сборка компонента под конкретный профиль (архитектура / платформа)."""

    profile_name: str = Field(..., description="Имя профиля сборки")
    exists: bool = Field(
        default=False,
        description="True — пакет для данного профиля найден в Artifactory",
    )
    variants: list[ConanVariant] = Field(
        default_factory=list,
        description="Список конкретных вариантов пакета",
    )
