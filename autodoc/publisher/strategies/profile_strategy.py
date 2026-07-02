"""Стратегия публикации профиль-центричной документации в Confluence."""

from typing import Any

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.profile_converter import ProfileCentricConverter
from autodoc.publisher.page_manager.passport_link_injector import inject_links_for_profiles
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class ProfileCentricStrategy(SinglePagePublishStrategy):
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
        """
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        kwargs.setdefault("link_injector", inject_links_for_profiles)
        super().__init__(
            converter=converter
            or self._make_converter(
                {"include_passport_links": kwargs.get("include_passport_links", True)}
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
