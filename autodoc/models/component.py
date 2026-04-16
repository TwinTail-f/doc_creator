"""
Доменные модели данных для компонентов платформы.

Используются на всём протяжении пайплайна — от парсинга манифестов
до финальной публикации в Confluence.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

OptionType = Literal["bool", "enum", "ANY", "string"]


class DefaultOptionsSet(BaseModel):
    """Описание одной дефолтной опции Conan-пакета (из поля default_options)."""

    name: str = Field(..., description="Имя опции")
    type: OptionType = Field(..., description="Тип значения опции")
    default_value: Any = Field(..., description="Значение по умолчанию")


def _parse_option_str(option_str: str) -> dict[str, Any]:
    """Convert 'pkg:shared=True, pkg:fPIC=False' → {'shared': 'True', 'fPIC': 'False'}.

    Package prefixes (e.g. ``mylib:``) are stripped so the result mirrors the
    structure of ``TotalOptionsSet.options`` and ``DefaultOptionsSet``.
    """
    result: dict[str, Any] = {}
    if not option_str:
        return result
    for part in option_str.split(","):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            key = k.strip().split(":")[-1].strip()
            result[key] = v.strip()
    return result


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
    parsed_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Опции в виде словаря {name: value} (пакетные префиксы удалены)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Автоматически заполняет ``parsed_options`` из ``options`` при создании."""
        if not self.parsed_options and self.options:
            # model fields are frozen after validation — use object.__setattr__
            object.__setattr__(self, "parsed_options", _parse_option_str(self.options))


class TotalOptionsSet(BaseModel):
    """A named set of resolved Conan build options from conan graph info 'options' field,
    keyed by ConanInputOptions.id."""

    id: str = Field(..., description='Option-set identifier matching ConanInputOptions.id (e.g. "1", "2")')
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Resolved Conan options from 'options' field in conan graph info: {name: value}",
    )


class ConanVariant(BaseModel):
    """Один конкретный вариант сборки Conan-пакета (конкретный package_id)."""

    package_id: str = Field(..., description="Идентификатор Conan-пакета")
    build_url: str = Field(default="", description="URL сборки в Artifactory")
    build_date: str = Field(default="", description="Дата сборки пакета")
    options_ref: str = Field(
        default="",
        description="Reference to Release.total_option_sets entry by id",
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
    """Per-profile settings and docker image, deduplicated at ParsedResult level."""

    profile_name: str = Field(..., description="Build profile name (unique key)")
    conan_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Conan settings for this profile",
    )
    docker_image: str = Field(
        default="",
        description="Docker image URL for this profile",
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
            "Resolved option sets from conan graph info 'options' field (шаг 3); "
            "ConanVariant.options_ref points here by id"
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
