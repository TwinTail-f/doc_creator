"""Общая база стратегий публикации страниц «комплекта для встраивания»."""

from typing import Any, ClassVar

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class EmbeddingKitPageStrategy(SinglePagePublishStrategy):
    """
    Публикует на одной странице Confluence справочный список Conan-ссылок
    компонентов платформы по каналам («комплект для встраивания») — без
    вкладок, паспортов и деталей сборки.

    ``KitFixedPageStrategy`` и ``KitLatestPageStrategy`` отличаются друг от
    друга ровно одним — формой Conan-ссылки (точная зафиксированная версия
    против диапазона/wildcard для последней сборки). Эта разница уже
    полностью инкапсулирована в соответствующем конвертере
    (``KitFixedConverter``/``KitLatestConverter``), поэтому самим стратегиям
    незачем дублировать конструктор и `_make_converter` — они лишь
    объявляют, каким классом конвертера пользоваться, через ``CONVERTER_CLS``.

    У обоих конвертеров нет понятия ссылки на паспорт, поэтому их
    ``enrich_with_passport_links()`` (унаследованный от ``BaseDataConverter``)
    ничего не делает — специально писать что-либо для этого не требуется.
    """

    DEFAULT_TEMPLATE: str = "embedding_kit.jinja2"
    CONVERTER_CLS: ClassVar[type[BaseDataConverter]]
    """Класс конвертера данных. Обязателен к переопределению в наследнике."""

    def __init__(
        self,
        *,
        converter: BaseDataConverter | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Инициализирует стратегию публикации страницы «комплекта для встраивания».

        Args:
            converter: Конвертер данных. Если не передан, создаётся экземпляр ``CONVERTER_CLS``.
            **kwargs: Остальные параметры для ``SinglePagePublishStrategy``.
                ``include_passport_links``, если передан, отбрасывается —
                у этой страницы нет понятия ссылок на паспорта.
        """
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        kwargs.pop("include_passport_links", None)
        super().__init__(
            converter=converter or self._make_converter({}),
            **kwargs,
        )

    @classmethod
    def _make_converter(cls, kwargs: dict[str, Any]) -> BaseDataConverter:
        """
        Создаёт экземпляр ``CONVERTER_CLS``.

        Args:
            kwargs: Не используется (страница не принимает параметров конвертера).

        Returns:
            Готовый экземпляр конвертера, объявленного в ``CONVERTER_CLS``.
        """
        return cls.CONVERTER_CLS()
