"""Стратегия публикации профиль-центричной документации в Confluence."""

from typing import Any

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.profile_converter import ProfileCentricConverter
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class ProfileCentricPageStrategy(SinglePagePublishStrategy):
    """
    Публикует профиль-центричную документацию релиза на одной странице Confluence.

    Реорганизует данные по схеме Профиль → Канал → Компонент.
    """

    DEFAULT_TEMPLATE: str = "profile_centric.jinja2"

    def __init__(
        self,
        *,
        converter: BaseDataConverter | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Инициализирует стратегию публикации профиль-центричной документации.

        Args:
            converter: Конвертер данных. Если не передан, создаётся ``ProfileCentricConverter``.
            **kwargs: Остальные параметры для ``SinglePagePublishStrategy``.
                ``include_passport_links``, если передан, потребляется здесь и
                уходит в конструктор конвертера — сама стратегия об этом флаге
                ничего не знает (см. ``ProfileCentricConverter.enrich_with_passport_links``).
        """
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        include_passport_links = kwargs.pop("include_passport_links", True)
        super().__init__(
            converter=converter or self._make_converter(
                {"include_passport_links": include_passport_links}
            ),
            **kwargs,
        )

    @staticmethod
    def _make_converter(kwargs: dict[str, Any]) -> BaseDataConverter:
        """
        Создаёт ``ProfileCentricConverter`` из аргументов конструктора.

        Args:
            kwargs: Словарь с ключом ``include_passport_links``.

        Returns:
            Готовый ``ProfileCentricConverter``.
        """
        return ProfileCentricConverter(
            include_passport_links=kwargs.get("include_passport_links", True),
        )
