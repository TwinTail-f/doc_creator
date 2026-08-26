"""Конвертер для страницы «Комплект для встраивания компонентов platform»."""

from autodoc.models.component import Component
from autodoc.models.release import Release
from autodoc.publisher.converters.base_kit_converter import BaseKitConverter


class KitFixedConverter(BaseKitConverter):
    """
    Конвертер для страницы с фиксированными версиями компонентов по каналам.

    Одна строка на каждый релиз (пара компонент+версия) — если у компонента
    в одном канале несколько зафиксированных версий, каждая выводится
    отдельной строкой, в порядке их следования в ``ParsedResult``.
    """

    VERSION_COLUMN_TITLE = "Фиксированная версия"

    def _build_row(
        self, comp: Component, rel: Release, platform_version: str
    ) -> tuple[str, str] | None:
        """
        Строит строку с точной Conan-ссылкой релиза.

        Args:
            comp: Компонент-владелец релиза.
            rel: Релиз с уже вычисленным ``conan_reference``.
            platform_version: Версия платформы, используется только как
                запасной вариант, если ``conan_reference`` не заполнен.

        Returns:
            Кортеж ``(dedup_key, reference)``. Дедупликация — по паре
            (имя компонента, версия), так как одна и та же версия одного
            компонента в одном канале не должна повторяться на странице.
        """
        reference = rel.conan_reference or (
            f"{comp.name}/{rel.version}@platform-{platform_version}/{rel.channel}"
        )
        dedup_key = f"{comp.name}::{rel.version}"
        return dedup_key, reference
