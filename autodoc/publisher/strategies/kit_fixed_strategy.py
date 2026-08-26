"""Стратегия публикации страницы «Комплект для встраивания компонентов platform»."""

from typing import Any

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.kit_fixed_converter import KitFixedConverter
from autodoc.publisher.page_manager.passport_link_injector import inject_links_noop
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class KitFixedPageStrategy(SinglePagePublishStrategy):
    """
    Публикует на одной странице Confluence список фиксированных версий
    компонентов платформы по каналам («комплект для встраивания»).

    В отличие от ``ReleasePageStrategy``/``ProfileCentricStrategy``, эта
    страница — простой справочный список Conan-ссылок без вкладок,
    паспортов и подробностей сборки, поэтому ссылки на паспорта не
    поддерживаются (``include_passport_links`` всегда ``False``).
    """

    DEFAULT_TEMPLATE: str = "embedding_kit.jinja2"

    def __init__(
        self,
        *,
        converter: BaseDataConverter | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Инициализирует стратегию публикации страницы фиксированных версий.

        Args:
            converter: Конвертер данных. Если не передан, создаётся ``KitFixedConverter``.
            **kwargs: Остальные параметры для ``SinglePagePublishStrategy``.
                ``include_passport_links``, если передан, игнорируется —
                у этой страницы нет понятия ссылок на паспорта.
        """
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        kwargs["link_injector"] = inject_links_noop
        kwargs["include_passport_links"] = False
        super().__init__(
            converter=converter or self._make_converter({}),
            **kwargs,
        )

    @staticmethod
    def _make_converter(kwargs: dict[str, Any]) -> BaseDataConverter:
        """
        Создаёт ``KitFixedConverter``.

        Args:
            kwargs: Не используется (страница не принимает параметров конвертера).

        Returns:
            Готовый ``KitFixedConverter``.
        """
        return KitFixedConverter()
