"""
Результат обогащения данными Conan, готовый к применению к моделям.

ReleaseConanData      — данные Conan для одного Release.
ProfileConanData      — данные Conan для одного ProfileBuild.
ConanEnrichmentResult — итоговый результат выполнения conan graph info.
"""

from dataclasses import dataclass, field
from typing import Any

from autodoc.parser.conan.models.conan_report import ConanComponentReport
from autodoc.models.conan_variant import ConanVariant
from autodoc.models.options import DefaultOptionsSet, TotalOptionsSet
from autodoc.models.types import ReleaseKey

# Тип лога ошибок: {comp_name: {version: {channel: {profile: [errors]}}}}
_ErrorLog = dict[str, dict[str, dict[str, dict[str, list]]]]


@dataclass
class ReleaseConanData:
    """Данные Conan для обогащения одного Release."""

    base_ref: str
    rrev: str
    full_version: str
    #: Дефолтные опции из поля ``default_options`` вывода conan graph info.
    default_options: list[DefaultOptionsSet]
    #: Разрешённые опции из поля ``options`` вывода conan graph info, сгруппированные по option_id.
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


@dataclass
class ConanEnrichmentResult:
    """Результат выполнения Conan graph info, готовый для применения к моделям."""

    release_data: dict[ReleaseKey, ReleaseConanData] = field(
        default_factory=dict
    )
    profile_data: dict[int, ProfileConanData] = field(default_factory=dict)
    errors: _ErrorLog = field(default_factory=dict)
    total_tasks: int = 0
    succeeded: int = 0
    failed: int = 0
    execution_report: list[ConanComponentReport] = field(default_factory=list)
