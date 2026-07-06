"""
View-model датаклассы паблишера.

В текущем виде типизирован только ``ConanVariantView`` — остальные view-model
(паспорта, профиль-центричный и полный вид релиза) представлены обычными
``dict[str, Any]``, формируемыми конвертерами напрямую. Полная типизация
всех view-model — планируемое улучшение, пока не реализованное.
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
    options_ref: str = ""
    conan_options: dict[str, Any] = field(default_factory=dict)
    # CSS-класс бейджа для каждой опции из conan_options, вычисленный по признаку
    # отличия от дефолтного значения компонента (не по самому значению).
    # 'autodoc-badge-def' — совпадает с дефолтом (или дефолт неизвестен),
    # 'autodoc-badge-t'/-f/-n' — отличается и приводится к True/False/иному.
    option_badges: dict[str, str] = field(default_factory=dict)
    # Предформатированная строка вида '-o pkg:opt=val -o dep:opt=val'
    # для подстановки напрямую в команду 'conan install'.
    install_options: str = ""
