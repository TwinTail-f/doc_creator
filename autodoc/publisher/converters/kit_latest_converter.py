"""Конвертер для страницы «Встраивание последних версий компонентов»."""

from autodoc.models.component import Component
from autodoc.models.release import Release
from autodoc.publisher.converters.base_kit_converter import BaseKitConverter


class KitLatestConverter(BaseKitConverter):
    """
    Конвертер для страницы со ссылками на последние сборки компонентов по каналам.

    В отличие от ``KitFixedConverter``, версия не фиксируется: вместо неё
    подставляется литеральный диапазон Conan ``[,include_prerelease]``,
    означающий «любая последняя сборка, включая пререлизы». Строка выводится
    один раз на компонент в канале, независимо от того, сколько у него в
    этом канале зафиксированных версий/релизов.
    """

    VERSION_COLUMN_TITLE = "Последняя сборка"

    def _build_row(
        self, comp: Component, rel: Release, platform_version: str
    ) -> tuple[str, str] | None:
        """
        Строит строку с «плавающей» Conan-ссылкой (без конкретной версии).

        Args:
            comp: Компонент-владелец релиза.
            rel: Релиз — используется только ради канала (``rel.channel``).
            platform_version: Версия платформы, подставляется в ``@platform-{...}``.

        Returns:
            Кортеж ``(dedup_key, reference)``. Дедупликация — по имени
            компонента: несколько зафиксированных версий одного компонента
            в одном канале должны схлопнуться в одну строку.
        """
        reference = f"{comp.name}/[,include_prerelease]@platform-{platform_version}/{rel.channel}"
        return comp.name, reference
