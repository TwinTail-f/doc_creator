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

# Тип лога ошибок: {comp_name: {version: {channel: {profile: [errors]}}}}
_ErrorLog = dict[str, dict[str, dict[str, dict[str, list]]]]


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
