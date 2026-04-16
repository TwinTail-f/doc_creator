"""
Типы данных результата выполнения Conan graph info.

Живут в ``models/`` — разделяются между слоями парсера и энричера
без привязки к внутренностям пакета ``conan/``.

``ReleaseConanData`` и ``ProfileConanData`` используют типизированные поля
из ``component.py`` (``DefaultOptionsSet``, ``TotalOptionsSet``, ``ConanVariant``),
устраняя дублирование промежуточных словарей и необходимость конверсии в
``DataEnricher``.
"""

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from autodoc.models.component import ConanVariant, DefaultOptionsSet, TotalOptionsSet

if TYPE_CHECKING:
    from autodoc.parser.conan.task_builder import ConanTask


@dataclass
class ConanRawResult:
    """Сырой результат одного вызова ``conan graph info``."""

    task: "ConanTask"
    success: bool
    data: dict[str, Any] | None
    error: str = ""


@dataclass
class ConanCommandRecord:
    """Запись об одном выполненном вызове ``conan graph info``."""

    command: str
    status: str  # "SUCCESS" | "FAILED"
    error: str = ""


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


@dataclass
class ReleaseConanData:
    """
    Данные Conan для обогащения одного Release.

    Поле ``default_options`` хранит уже типизированные объекты ``DefaultOptionsSet``
    (из поля ``default_options`` в JSON conan graph info).

    Поле ``total_options`` хранит типизированные объекты ``TotalOptionsSet``
    (из поля ``options`` в JSON conan graph info), сгруппированные по option_id.
    """

    base_ref: str
    rrev: str
    full_version: str
    default_options: list[DefaultOptionsSet]
    total_options: list[TotalOptionsSet]
    patches: list[str]
    dependencies: list[str]
    artifactory_url: str


@dataclass
class ProfileConanData:
    """
    Данные Conan для обогащения одного ProfileBuild.

    Поле ``variants`` хранит уже типизированные объекты ``ConanVariant``
    (а не сырые словари), что исключает дополнительную конверсию в ``DataEnricher``.
    """

    conan_settings: dict[str, Any]
    exists: bool
    variants: list[ConanVariant]


# Тип лога ошибок: {comp_name: {version: {channel: {profile: [errors]}}}}
_ErrorLog = dict[str, dict[str, dict[str, dict[str, list]]]]


@dataclass
class ConanEnrichmentResult:
    """
    Результат выполнения Conan graph info, готовый для применения к моделям.

    Не мутирует модели — передаётся в ``DataEnricher.apply_conan_results()``.
    """

    release_data: dict[tuple[str, str, str], ReleaseConanData] = field(
        default_factory=dict
    )
    profile_data: dict[int, ProfileConanData] = field(default_factory=dict)
    errors: _ErrorLog = field(default_factory=dict)
    total_tasks: int = 0
    succeeded: int = 0
    failed: int = 0
    execution_report: list[ConanComponentReport] = field(default_factory=list)
