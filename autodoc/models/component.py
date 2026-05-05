"""
Доменные модели данных для компонентов платформы.

Используются на всём протяжении пайплайна — от парсинга манифестов
до финальной публикации в Confluence.
"""

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, PrivateAttr, model_validator

OptionType = Literal["bool", "enum", "ANY", "string"]


def _parse_option_str(option_str: str) -> dict[str, str]:
    """Преобразует строку 'pkg:shared=True, pkg:fPIC=False' в {'shared': 'True', 'fPIC': 'False'}.

    Пакетные префиксы (например ``mylib:``) удаляются, чтобы результат
    соответствовал структуре ``TotalOptionsSet.options`` и ``DefaultOptionsSet``.
    """
    result: dict[str, str] = {}
    if not option_str:
        return result
    for part in option_str.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            key = k.split(":")[-1].strip()
            result[key] = v.strip()
    return result


class DefaultOptionsSet(BaseModel):
    """Описание одной дефолтной опции Conan-пакета (из поля default_options)."""

    name: str = Field(..., description="Имя опции")
    type: OptionType = Field(..., description="Тип значения опции")
    default_value: Any = Field(..., description="Значение по умолчанию")


class ConanInputOptions(BaseModel):
    """Один набор входных опций сборки Conan (id + строка опций + разобранный словарь).

    ``options`` хранит исходную строку опций (используется при передаче в CLI).
    ``parsed_options`` — те же опции в виде словаря ``{name: value}``,
    аналогично ``TotalOptionsSet.options`` и ``DefaultOptionsSet``,
    для единообразного представления в итоговом JSON.
    """

    id: str = Field(..., description='Идентификатор набора опций (например "1", "2")')
    options: str = Field(
        default="",
        description='Строка опций (например "component:shared=False, component:fPIC=True")',
    )
    parsed_options: dict[str, str] = Field(
        default_factory=dict,
        description="Опции в виде словаря {name: value} (пакетные префиксы удалены)",
    )

    @model_validator(mode="after")
    def _fill_parsed_options(self) -> Self:
        """Автоматически заполняет ``parsed_options`` из ``options`` при создании."""
        if not self.parsed_options and self.options:
            self.parsed_options = _parse_option_str(self.options)
        return self


class TotalOptionsSet(BaseModel):
    """Именованный набор разрешённых опций сборки Conan из поля ``options`` вывода ``conan graph info``,
    привязанный к идентификатору ``ConanInputOptions.id``."""

    id: str = Field(
        ...,
        description='Идентификатор набора опций, совпадает с ConanInputOptions.id (например "1", "2")',
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Разрешённые опции Conan из поля options вывода conan graph info: {name: value}",
    )


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

    build_option_sets: list[ConanInputOptions] = Field(
        default_factory=list,
        description="Наборы конфигураций сборки Conan (ConanInputOptions — входные данные, шаг 2)",
    )

    default_options: list[DefaultOptionsSet] = Field(
        default_factory=list,
        description="Список дефолтных опций из conan graph info (поле default_options, шаг 3)",
    )
    patches: list[str] = Field(default_factory=list, description="Список патчей")
    dependencies: list[str] = Field(
        default_factory=list, description="Список зависимостей"
    )

    is_header_only: bool = Field(
        default=False,
        description="True — header-only компонент (нет бинарных артефактов)",
    )

    total_option_sets: list[TotalOptionsSet] = Field(
        default_factory=list,
        description=(
            "Разрешённые наборы опций из поля options вывода conan graph info (шаг 3); "
            "ConanVariant.options_ref ссылается сюда по идентификатору"
        ),
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
