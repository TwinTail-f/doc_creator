"""
Финальная модель результата пайплайна парсера.
"""

from pydantic import BaseModel, Field

from autodoc.models.component import Component, ProfileDefinition


class ParsedResult(BaseModel):
    """
    Финальная модель данных после выполнения всего пайплайна парсера.

    Создаётся на шаге ``FinalizeStep`` и передаётся в паблишер.
    Сериализуется в ``parsed_data.json`` при ``save_intermediate=True``.
    """

    generated_at: str = Field(..., description="Дата и время генерации в ISO 8601")
    platform_version: str = Field(..., description="Версия платформы (из конфига)")
    profile_definitions: list[ProfileDefinition] = Field(
        default_factory=list,
        description="Deduplicated profile definitions (conan_settings + docker_image) for all profiles encountered across all components",
    )
    components: list[Component] = Field(
        default_factory=list,
        description="Список всех обработанных компонентов платформы",
    )
