"""Абстрактный базовый класс конвертеров для страниц «комплекта встраивания»."""

from abc import abstractmethod
from typing import Any, ClassVar

from autodoc.common.logger import logger
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.publisher.converters.base_data_converter import BaseDataConverter


class BaseKitConverter(BaseDataConverter):
    """Базовый конвертер страниц «комплекта встраивания»: Conan-ссылки по каналам."""

    CHANNEL_ORDER: ClassVar[tuple[str, ...]] = ("tech", "trusted", "slow", "fast")
    """Порядок отображения каналов; остальные выводятся после них по алфавиту."""

    VERSION_COLUMN_TITLE: ClassVar[str] = ""
    """Заголовок второй колонки таблицы."""

    @abstractmethod
    def _build_row(self, comp: Component, rel: Release) -> tuple[str, str] | None:
        """
        Строит строку таблицы для пары «компонент, релиз».

        Returns:
            ``(dedup_key, reference)`` или ``None``, если строка не нужна.
        """

    def _order_channels(self, channels: dict[str, list[str]]) -> list[dict[str, Any]]:
        """Упорядочивает каналы согласно ``CHANNEL_ORDER``."""
        known = [ch for ch in self.CHANNEL_ORDER if ch in channels]
        unknown = sorted(ch for ch in channels if ch not in self.CHANNEL_ORDER)
        return [{"name": ch, "references": channels[ch]} for ch in known + unknown]

    def convert(self, data: ParsedResult) -> dict[str, Any]:
        """Возвращает view-model страницы: версию платформы, заголовок колонки и каналы."""
        logger.debug(f"Конвертация в вид {self.__class__.__name__}")

        channels: dict[str, list[str]] = {}
        seen: dict[str, set[str]] = {}

        for comp in data.components:
            for rel in comp.releases:
                row = self._build_row(comp, rel)
                if row is None:
                    continue
                dedup_key, reference = row

                channel_seen = seen.setdefault(rel.channel, set())
                if dedup_key in channel_seen:
                    continue
                channel_seen.add(dedup_key)
                channels.setdefault(rel.channel, []).append(reference)

        return {
            "platform_version": data.platform_version,
            "version_column_title": self.VERSION_COLUMN_TITLE,
            "channels": self._order_channels(channels),
        }
