"""
Доменные модели данных для компонентов платформы.

Используются на всём протяжении пайплайна — от парсинга манифестов
до финальной публикации в Confluence.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

OptionType = Literal["bool", "enum", "ANY", "string"]


class BuildOptionSet(BaseModel):
    """Один набор опций сборки Conan с идентификатором для корреляции задач."""

    id: str = Field(..., description='Идентификатор набора опций (например "1", "2")')
    options: str = Field(
        default="",
        description='Строка опций (например "component:shared=False, component:fPIC=True")',
    )


class OptionDefinition(BaseModel):
    """Описание одной дефолтной опции Conan-пакета."""

    name: str = Field(..., description="Имя опции")
    type: OptionType = Field(..., description="Тип значения опции")
    default_value: Any = Field(..., description="Значение по умолчанию")


class ConanVariant(BaseModel):
    """Один конкретный вариант сборки Conan-пакета (конкретный package_id)."""

    package_id: str = Field(..., description="Идентификатор Conan-пакета")
    build_url: str = Field(default="", description="URL сборки в Artifactory")
    build_date: str = Field(default="", description="Дата сборки пакета")
    conan_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Фактические опции конкретной сборки: {name: value}",
    )


class ProfileBuild(BaseModel):
    """Сборка компонента под конкретный профиль (архитектура / платформа)."""

    profile_name: str = Field(..., description="Имя профиля сборки")
    conan_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Настройки Conan для профиля",
    )
    exists: bool = Field(
        default=False,
        description="True — пакет для данного профиля найден в Artifactory",
    )
    docker_image: str = Field(
        default="",
        description="URL Docker-образа для сборки профиля",
    )
    variants: list[ConanVariant] = Field(
        default_factory=list,
        description="Список конкретных вариантов пакета",
    )


class Release(BaseModel):
    """Один релиз (версия) компонента с привязкой к платформе и каналу."""

    version: str = Field(..., description="Версия компонента")
    platform: str = Field(..., description="Целевая платформа")
    channel: str = Field(..., description='Conan-канал (например "fast")')
    git_url: str = Field(..., description="URL репозитория в Git/TFS")

    conan_reference: str = Field(
        default="", description="Ссылка Conan (name/version@user/channel)"
    )
    artifactory_url: str = Field(default="", description="URL пакета в Artifactory")

    build_option_sets: list[BuildOptionSet] = Field(
        default_factory=list,
        description="Наборы конфигураций сборки Conan",
    )

    default_options: list[OptionDefinition] = Field(
        default_factory=list,
        description="Список дефолтных опций из conan graph info",
    )
    patches: list[str] = Field(default_factory=list, description="Список патчей")
    dependencies: list[str] = Field(
        default_factory=list, description="Список зависимостей"
    )

    is_header_only: bool = Field(
        default=False,
        description="True — header-only компонент (нет бинарных артефактов)",
    )

    profile_builds: list[ProfileBuild] = Field(
        default_factory=list,
        description="Список сборок по профилям",
    )

    _build_option_sets_internal: dict[str, str] = PrivateAttr(default_factory=dict)


class Component(BaseModel):
    """Компонент платформы — верхний уровень доменной модели."""

    name: str = Field(..., description="Уникальное имя компонента")
    description: str = Field(default="", description="Краткое описание компонента")
    git_project: str = Field(default="", description="Проект в TFS/Git")
    git_repo: str = Field(default="", description="Имя репозитория")
    releases: list[Release] = Field(
        default_factory=list,
        description="Список релизов компонента",
    )


__all__ = [
    "OptionType",
    "BuildOptionSet",
    "OptionDefinition",
    "ConanVariant",
    "ProfileBuild",
    "Release",
    "Component",
]
