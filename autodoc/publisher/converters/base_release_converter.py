"""Абстрактный базовый класс трансформеров документации релиза."""

from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.base_data_converter import BaseDataConverter


class BaseReleaseConverter(BaseDataConverter):
    """
    Базовый класс конвертеров документации релиза.

    Конкретные виды реализуют ``transform()``. Ссылки на паспорта
    компонентов конвертер не строит — они внедряются отдельно, уже после
    публикации паспортов, через ``inject_links`` / ``inject_links_for_profiles``.
    """

    def __init__(
        self,
        include_passport_links: bool = True,
    ) -> None:
        """
        Args:
            include_passport_links: Передавать ли флаг включения ссылок на паспорта
                                    в view-model шаблона.
        """
        self._include_passport_links: bool = include_passport_links

    def _base_view_model(self, data: ParsedResult) -> dict[str, Any]:
        """Строит общие для всех видов релиза поля view-model.

        Args:
            data: Полный набор данных парсера.

        Returns:
            Словарь с полями ``platform_version`` и ``include_passport_links``.
        """
        return {
            "platform_version": data.platform_version,
            "include_passport_links": self._include_passport_links,
        }
