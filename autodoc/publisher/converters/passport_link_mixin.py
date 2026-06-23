"""Вспомогательные типы и миксин для конвертеров документации релиза."""

from typing import NamedTuple, Any


class _VariantOpts(NamedTuple):
    """Опции сборки для одного варианта Conan в view-model."""

    conan_options: dict[str, Any]
    install_options_override: str | None = None


class PassportLinkMixin:
    """
    Миксин, хранящий флаг включения ссылок на паспорта компонентов.

    Классы-наследники должны устанавливать ``_include_passport_links``
    в своём ``__init__``.
    Реальные ссылки на паспорта внедряются ``PassportPageRegistry``
    после публикации паспортов — через ``inject_links`` / ``inject_links_for_profiles``.
    """

    _include_passport_links: bool
