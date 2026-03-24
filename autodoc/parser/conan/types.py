"""
Типы данных результата выполнения Conan graph info.

Вынесены в отдельный модуль чтобы разорвать потенциальный циклический
импорт между conan_manager.py и data_enricher.py.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class ReleaseConanData:
    """Данные Conan для обогащения одного Release."""

    base_ref: str
    rrev: str
    full_version: str
    default_options: List[Dict[str, Any]]
    patches: List[str]
    dependencies: List[str]
    artifactory_url: str


@dataclass
class ProfileConanData:
    """Данные Conan для обогащения одного ProfileBuild."""

    conan_settings: Dict[str, Any]
    exists: bool
    variants: List[Dict[str, Any]]


# Тип лога ошибок: {comp_name: {version: {channel: {profile: [errors]}}}}
_ErrorLog = Dict[str, Dict[str, Dict[str, Dict[str, List]]]]


@dataclass
class ConanEnrichmentResult:
    """
    Результат выполнения Conan graph info, готовый для применения к моделям.

    Не мутирует модели — передаётся в ``DataEnricher.apply_conan_results()``.
    """

    # Данные для обогащения Release: (comp_name, version, channel) → данные
    release_data: Dict[Tuple[str, str, str], ReleaseConanData] = field(default_factory=dict)
    # Данные для обогащения ProfileBuild: id(pb) → данные
    profile_data: Dict[int, ProfileConanData] = field(default_factory=dict)
    # Лог ошибок
    errors: _ErrorLog = field(default_factory=dict)
    total_tasks: int = 0
    succeeded: int = 0
    failed: int = 0
