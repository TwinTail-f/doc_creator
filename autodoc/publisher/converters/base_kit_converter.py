"""Абстрактный базовый класс конвертеров для страниц «комплекта встраивания»."""

from abc import abstractmethod
from typing import Any, ClassVar

from autodoc.common.logger import logger
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.publisher.converters.base_data_converter import BaseDataConverter


class BaseKitConverter(BaseDataConverter):
    """
    Общая логика конвертеров «комплекта встраивания компонентов platform».

    Обе конкретные страницы (фиксированные версии и последние сборки) имеют
    одинаковую форму: список каналов в фиксированном порядке, в каждом —
    нумерованный список Conan-ссылок. Различается только то, какая ссылка
    строится для каждого релиза и как определяется дедупликация строк внутри
    канала — это делегируется ``_build_row()`` в конкретном подклассе.

    Порядок компонентов внутри канала не меняется (не сортируется) — строки
    идут в том порядке, в котором компоненты и их релизы перечислены в
    ``ParsedResult.components`` (порядок манифеста).
    """

    CHANNEL_ORDER: ClassVar[tuple[str, ...]] = ("tech", "trusted", "slow", "fast")
    """Порядок отображения каналов на странице. Каналы вне этого списка
    (нестандартные/будущие) выводятся после перечисленных, в алфавитном
    порядке — чтобы страница не «терялась» молча при появлении нового канала."""

    VERSION_COLUMN_TITLE: ClassVar[str] = ""
    """Заголовок второй колонки таблицы (переопределяется в подклассах)."""

    @abstractmethod
    def _build_row(
        self, comp: Component, rel: Release, platform_version: str
    ) -> tuple[str, str] | None:
        """
        Строит одну строку таблицы для пары «компонент, релиз».

        Args:
            comp: Компонент-владелец релиза.
            rel: Релиз (версия в конкретном канале).
            platform_version: Версия платформы (``ParsedResult.platform_version``).

        Returns:
            Кортеж ``(dedup_key, reference)``, где ``dedup_key`` используется
            для дедупликации строк внутри канала (см. ``convert()``), а
            ``reference`` — отображаемый текст строки. ``None``, если для
            этой пары строка не строится (например, релиз пропускается).
        """

    def _order_channels(self, channels: dict[str, list[str]]) -> list[dict[str, Any]]:
        """
        Упорядочивает каналы согласно ``CHANNEL_ORDER``, остальные — по алфавиту в конце.

        Args:
            channels: Словарь ``{имя_канала: [строки таблицы]}``.

        Returns:
            Список словарей ``{'name': ..., 'references': [...]}`` в итоговом
            порядке отображения. Каналы без строк не включаются.
        """
        known = [ch for ch in self.CHANNEL_ORDER if ch in channels]
        unknown = sorted(ch for ch in channels if ch not in self.CHANNEL_ORDER)
        return [{"name": ch, "references": channels[ch]} for ch in known + unknown]

    def convert(self, data: ParsedResult) -> dict[str, Any]:
        """
        Возвращает view-model страницы «комплекта встраивания».

        Args:
            data: Данные парсера.

        Returns:
            Словарь с полями ``platform_version``, ``version_column_title``
            и ``channels`` (список каналов с их строками).
        """
        logger.debug(f"Конвертация в вид {self.__class__.__name__}")

        channels: dict[str, list[str]] = {}
        seen: dict[str, set[str]] = {}

        for comp in data.components:
            for rel in comp.releases:
                row = self._build_row(comp, rel, data.platform_version)
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
