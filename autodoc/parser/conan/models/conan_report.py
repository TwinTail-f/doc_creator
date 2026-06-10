"""
Диагностические отчёты Conan graph info, группирующие результаты
по компонентам и профилям.
"""

from dataclasses import dataclass, field

from autodoc.parser.conan.models.conan_raw_result import ConanCommandRecord


@dataclass
class ConanProfileReport:
    """Все вызовы conan graph info для одного профиля."""

    profile_name: str
    commands: list[ConanCommandRecord] = field(default_factory=list)


@dataclass
class ConanComponentReport:
    """Диагностический отчёт по всем вызовам одного компонента/версии/канала."""

    component: str
    version: str
    channel: str
    # profile_name → отчёт профиля
    profiles: dict[str, ConanProfileReport] = field(default_factory=dict)
