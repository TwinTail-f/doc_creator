"""
View-model датаклассы паблишера.

Типизированный контракт между трансформерами и шаблонами Jinja2.
Используют стандартные dataclass (не Pydantic) — данные уже
провалидированы парсером, повторная валидация не нужна.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConanVariantView:
    """Вид одного варианта сборки для шаблонов паблишера."""

    package_id: str
    build_url: str
    build_date: str
    conan_options: dict[str, Any] = field(default_factory=dict)
    # Предформатированная строка вида '-o pkg:opt=val -o dep:opt=val'
    # для подстановки напрямую в команду 'conan install'.
    install_options: str = ""


@dataclass
class ProfileBuildView:
    """Вид одной сборки профиля для шаблонов паблишера."""

    profile_name: str
    conan_settings: dict[str, Any] = field(default_factory=dict)
    exists: bool = False
    docker_image: str = ""
    variants: list[ConanVariantView] = field(default_factory=list)


__all__ = [
    "ConanVariantView",
    "ProfileBuildView",
]
