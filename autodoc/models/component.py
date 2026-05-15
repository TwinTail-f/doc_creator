"""
Доменная модель компонента платформы.

Component — верхний уровень доменной модели.
"""

from pydantic import BaseModel, Field

from autodoc.models.release import Release


class Component(BaseModel):
    """Компонент платформы — верхний уровень доменной модели."""

    name: str = Field(..., description="Уникальное имя компонента")
    description: str = Field(default="", description="Краткое описание компонента")
    git_project: str = Field(default="", description="Проект в TFS/Git")
    git_repo: str = Field(default="", description="Имя репозитория")
    git_url: str = Field(default="", description="URL репозитория в Git/TFS")
    is_header_only: bool = Field(
        default=False,
        description="True — header-only компонент (нет бинарных артефактов)",
    )
    releases: list[Release] = Field(
        default_factory=list,
        description="Список релизов компонента",
    )
