"""
Типы данных результата выполнения Conan graph info.

Живут в ``models/`` — разделяются между слоями парсера и энричера
без привязки к внутренностям пакета ``conan/``.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReleaseConanData:
    """Данные Conan для обогащения одного Release."""

    base_ref: str
    rrev: str
    full_version: str
    default_options: list[dict[str, Any]]
    patches: list[str]
    dependencies: list[str]
    artifactory_url: str


@dataclass
class ProfileConanData:
    """Данные Conan для обогащения одного ProfileBuild."""

    conan_settings: dict[str, Any]
    exists: bool
    variants: list[dict[str, Any]]


# Тип лога ошибок: {comp_name: {version: {channel: {profile: [errors]}}}}
_ErrorLog = dict[str, dict[str, dict[str, dict[str, list]]]]


@dataclass
class ConanEnrichmentResult:
    """
    Результат выполнения Conan graph info, готовый для применения к моделям.

    Не мутирует модели — передаётся в ``DataEnricher.apply_conan_results()``.
    """

    # Данные для обогащения Release: (comp_name, version, channel) → данные
    release_data: dict[tuple[str, str, str], ReleaseConanData] = field(
        default_factory=dict
    )
    # Данные для обогащения ProfileBuild: id(pb) → данные
    profile_data: dict[int, ProfileConanData] = field(default_factory=dict)
    # Лог ошибок
    errors: _ErrorLog = field(default_factory=dict)
    total_tasks: int = 0
    succeeded: int = 0
    failed: int = 0
