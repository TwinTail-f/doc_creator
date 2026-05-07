"""Mixin that adds passport link support to converters."""

from typing import NamedTuple, Any

_DEFAULT_PASSPORT_PATTERN: str | None = None
"""
Шаблон URL паспорта по умолчанию.

Намеренно ``None``: паспортная ссылка всегда должна внедряться
``PassportPageRegistry`` после публикации. До заполнения реестра
ссылка недоступна, поэтому шаблон отображает «—» вместо нерабочего URL.
Передайте явный ``passport_page_pattern`` в конструктор трансформера,
только если вы знаете URL заранее.
"""


class _VariantOpts(NamedTuple):
    """Build options for a single Conan variant view."""

    conan_options: dict[str, Any]
    install_options_override: str | None = None


class PassportLinkMixin:
    """
    Миксин, добавляющий поддержку ссылок на паспорта компонентов.

    Устраняет дублирование одинаковых ``_DEFAULT_PASSPORT_PATTERN`` и
    ``_passport_link()`` из ``BaseReleaseConverter`` и
    ``ProfileCentricConverter``.

    Классы-наследники должны устанавливать ``_include_passport_links``
    и ``_pattern`` в своём ``__init__`` до первого обращения к методу.
    """

    _include_passport_links: bool
    _pattern: str | None

    def _passport_link(self, comp_name: str, version: str) -> str | None:
        """
        Формирует ссылку на паспорт компонента.

        Args:
            comp_name: Имя компонента.
            version: Версия релиза.

        Returns:
            URL паспорта, построенный по ``_pattern``, или ``None``,
            если ссылки отключены (``_include_passport_links is False``)
            либо шаблон не задан (реестр ещё не заполнен).
        """
        if not self._include_passport_links or not self._pattern:
            return None
        return self._pattern.format(
            component_name=comp_name.replace(" ", "+"),
            release_version=version.replace(" ", "+"),
        )
