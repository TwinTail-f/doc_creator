"""
Финальная модель результата пайплайна парсера.
"""

from pydantic import BaseModel, Field

from autodoc.models.component import Component

class ParsedResult(BaseModel):
    """
    Финальная модель данных после выполнения всего пайплайна парсера.

    Создаётся на шаге ``FinalizeStep`` и передаётся в паблишер.
    Сериализуется в ``parsed_data.json`` при ``save_intermediate=True``.
    """

    generated_at: str = Field(..., description="Дата и время генерации в ISO 8601")
    platform_version: str = Field(..., description="Версия платформы (из конфига)")
    components: list[Component] = Field(
        default_factory=list,
        description="Список всех обработанных компонентов платформы",
    )
