"""
Модели опций сборки Conan-пакетов.

DefaultOptionsSet   — одна дефолтная опция пакета.
ConanInputOptions   — набор входных опций сборки.
TotalOptionsSet     — разрешённый набор опций из вывода conan graph info.
"""

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

OptionType = Literal["bool", "enum", "ANY", "string"]


def _parse_option_str(option_str: str) -> dict[str, str]:
    """
    Преобразует строку 'pkg:shared=True, pkg:fPIC=False' в {'shared': 'True', 'fPIC': 'False'}.

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
    """
    Один набор входных опций сборки Conan (id + строка опций + разобранный словарь).

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
    """
    Именованный набор разрешённых опций сборки Conan из поля ``options`` вывода ``conan graph info``,
    привязанный к идентификатору ``ConanInputOptions.id``.
    """

    id: str = Field(
        ...,
        description='Идентификатор набора опций, совпадает с ConanInputOptions.id (например "1", "2")',
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Разрешённые опции Conan из поля options вывода conan graph info: {name: value}",
    )
