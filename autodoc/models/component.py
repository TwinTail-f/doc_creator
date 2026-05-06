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
    releases: list[Release] = Field(
        default_factory=list,
        description="Список релизов компонента",
    )
