"""
Модель одного релиза (версии) компонента.

Release — версия компонента с привязкой к платформе и каналу.
"""

from pydantic import BaseModel, Field

from autodoc.models.conan_variant import ConanVariant, ProfileBuild  # noqa: F401
from autodoc.models.options import ConanInputOptions, DefaultOptionsSet, TotalOptionsSet


class Release(BaseModel):
    """Один релиз (версия) компонента с привязкой к платформе и каналу."""

    version: str = Field(..., description="Версия компонента")
    platform: str = Field(..., description="Целевая платформа")
    channel: str = Field(..., description='Conan-канал (например "fast")')

    conan_reference: str = Field(default="", description="Ссылка Conan (name/version@user/channel)")
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
    dependencies: list[str] = Field(default_factory=list, description="Список зависимостей")

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
