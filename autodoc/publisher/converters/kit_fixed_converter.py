"""Конвертер для страницы «Комплект для встраивания компонентов platform»."""

from autodoc.models.component import Component
from autodoc.models.release import Release
from autodoc.publisher.converters.base_kit_converter import BaseKitConverter


class KitFixedConverter(BaseKitConverter):
    """Конвертер страницы с фиксированными версиями компонентов по каналам."""

    VERSION_COLUMN_TITLE = "Фиксированная версия"

    def _build_row(self, comp: Component, rel: Release) -> tuple[str, str] | None:
        """Строит строку с точной Conan-ссылкой; дедупликация по паре «компонент + версия»."""
        reference = rel.conan_reference or (
            f"{comp.name}/{rel.version}@platform-{rel.platform}/{rel.channel}"
        )
        return f"{comp.name}::{rel.version}", reference
