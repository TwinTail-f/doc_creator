"""
Доменные модели данных для компонентов платформы.

Используются на всём протяжении пайплайна — от парсинга манифестов
до финальной публикации в Confluence.
"""
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, PrivateAttr

# 1.6 Именованное множество допустимых типов опции Conan
OptionType = Literal['bool', 'enum', 'ANY', 'string']


class SvaceReport(BaseModel):
    """Ссылка на отчёт статического анализатора Svace для профиля сборки."""

    profile: str = Field(..., description='Имя профиля сборки')


class OptionDefinition(BaseModel):
    """Описание одной дефолтной опции Conan-пакета."""

    name: str = Field(..., description='Имя опции')
    type: OptionType = Field(..., description='Тип значения опции')  # 1.6
    default_value: Any = Field(..., description='Значение по умолчанию')


class ConanVariant(BaseModel):
    """Один конкретный вариант сборки Conan-пакета (конкретный package_id)."""

    package_id: str = Field(..., description='Идентификатор Conan-пакета')
    build_url: str = Field(default='', description='URL сборки в Artifactory')
    build_date: str = Field(default='', description='Дата сборки пакета')
    conan_options: Dict[str, Any] = Field(
        default_factory=dict,
        description='Фактические опции конкретной сборки: {name: value}',
    )
    # 1.1 option_set_id и option_set_str удалены — артефакты пайплайна,
    #     не часть доменной модели. Остаются только в ConanEnrichData.


class ProfileBuild(BaseModel):
    """Сборка компонента под конкретный профиль (архитектура / платформа)."""

    profile_name: str = Field(..., description='Имя профиля сборки')
    conan_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description='Настройки Conan для профиля',
    )
    exists: bool = Field(          # 1.2 было: pb_exist
        default=False,
        description='True — пакет для данного профиля найден в Artifactory',
    )
    docker_image: str = Field(     # 1.2 было: profile_docker_url
        default='',
        description='URL Docker-образа для сборки профиля',
    )
    variants: List[ConanVariant] = Field(
        default_factory=list,
        description='Список конкретных вариантов пакета',
    )


class Release(BaseModel):
    """Один релиз (версия) компонента с привязкой к платформе и каналу."""

    version: str = Field(..., description='Версия компонента')
    platform: str = Field(..., description='Целевая платформа')
    channel: str = Field(..., description='Conan-канал (например "stable")')
    git_url: str = Field(..., description='URL репозитория в Git/TFS')

    # 1.3 git_project и git_repo удалены из Release — они есть в Component.
    #     OptionsResolver берёт их из Component, который получает вместе с релизом.

    conan_reference: str = Field(default='', description='Ссылка Conan (name/version@user/channel)')
    artifactory_url: str = Field(default='', description='URL пакета в Artifactory')

    # 1.4 было: conan_options — переименовано, чтобы устранить коллизию смыслов.
    #     ConanVariant.conan_options — фактические опции конкретной сборки {name: value}.
    #     Release.build_option_sets — наборы конфигураций сборки {id: option_string}.
    build_option_sets: Dict[str, str] = Field(
        default_factory=dict,
        description='Наборы опций сборки: {id: "option_string"}',
    )

    default_options: List[OptionDefinition] = Field(
        default_factory=list,
        description='Список дефолтных опций из conan graph info',
    )
    patches: List[str] = Field(default_factory=list, description='Список патчей')
    dependencies: List[str] = Field(default_factory=list, description='Список зависимостей')

    svace_report: SvaceReport = Field(
        default_factory=lambda: SvaceReport(profile=''),
        description='Отчёт Svace для данного релиза',
    )
    is_header_only: bool = Field(  # 1.5 было: is_header_only_component
        default=False,
        description='True — header-only компонент (нет бинарных артефактов)',
    )

    profile_builds: List[ProfileBuild] = Field(
        default_factory=list,
        description='Список сборок по профилям',
    )

    # Внутреннее хранилище наборов опций для шага Conan — не сериализуется
    _build_option_sets_internal: Dict[str, str] = PrivateAttr(default_factory=dict)


class Component(BaseModel):
    """Компонент платформы — верхний уровень доменной модели."""

    name: str = Field(..., description='Уникальное имя компонента')
    description: str = Field(default='', description='Краткое описание компонента')
    git_project: str = Field(default='', description='Проект в TFS/Git')
    git_repo: str = Field(default='', description='Имя репозитория')
    releases: List[Release] = Field(
        default_factory=list,
        description='Список релизов компонента',
    )

    # 1.7 extra='allow' убран — маскировал ошибки.
    #     Pydantic v2 по умолчанию игнорирует лишние поля (extra='ignore').


__all__ = [
    'OptionType',
    'SvaceReport',
    'OptionDefinition',
    'ConanVariant',
    'ProfileBuild',
    'Release',
    'Component',
]
