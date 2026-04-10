"""Абстрактный базовый класс трансформеров данных и миксин для ссылок на паспорта."""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.models.parsed_result import ParsedResult

_DEFAULT_PASSPORT_PATTERN: str = (
    "/spaces/DOC/pages/{component_name}+{release_version}"
)


class PassportLinkMixin:
    """
    Миксин, добавляющий поддержку ссылок на паспорта компонентов.

    Устраняет дублирование одинаковых ``_DEFAULT_PASSPORT_PATTERN`` и
    ``_passport_link()`` из ``BaseReleaseTransformer`` и
    ``ProfileCentricTransformer``.

    Классы-наследники должны устанавливать ``_include_passport_links``
    и ``_pattern`` в своём ``__init__`` до первого обращения к методу.
    """

    _include_passport_links: bool
    _pattern: str

    def _passport_link(self, comp_name: str, version: str) -> str | None:
        """
        Формирует ссылку на паспорт компонента.

        Args:
            comp_name: Имя компонента.
            version: Версия релиза.

        Returns:
            URL паспорта, построенный по ``_pattern``, или ``None``,
            если ссылки отключены (``_include_passport_links is False``).
        """
        if not self._include_passport_links:
            return None
        return self._pattern.format(
            component_name=comp_name.replace(" ", "+"),
            release_version=version.replace(" ", "+"),
        )


class BaseDataTransformer(ABC):
    """
    Абстрактный базовый класс трансформеров данных.

    Преобразует ``ParsedResult`` в view-model, пригодный для рендеринга
    конкретного шаблона. Следует паттерну Стратегия.
    """

    @abstractmethod
    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Преобразует данные в view-model для шаблона.

        Args:
            data: Полный набор данных парсера.

        Returns:
            Словарь с иерархической структурой, готовый для шаблонизатора.
        """
