"""Конвертер для страницы «Встраивание последних версий компонентов»."""

from autodoc.models.component import Component
from autodoc.models.release import Release
from autodoc.publisher.converters.base_kit_converter import BaseKitConverter


class KitLatestConverter(BaseKitConverter):
    """Конвертер страницы со ссылками на последние сборки компонентов по каналам."""

    VERSION_COLUMN_TITLE = "Последняя сборка"

    def _build_row(self, comp: Component, rel: Release) -> tuple[str, str] | None:
        """Строит ссылку с диапазоном ``[*,include_prerelease]``; дедупликация по имени компонента."""
        reference = f"{comp.name}/[*,include_prerelease]@platform-{rel.platform}/{rel.channel}"
        return comp.name, reference
