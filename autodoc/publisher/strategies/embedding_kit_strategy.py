"""Общая база стратегий публикации страниц «комплекта для встраивания»."""

from typing import Any, ClassVar

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class EmbeddingKitPageStrategy(SinglePagePublishStrategy):
    """Базовая стратегия публикации страниц «комплекта для встраивания»."""

    DEFAULT_TEMPLATE: str = "embedding_kit.jinja2"
    CONVERTER_CLS: ClassVar[type[BaseDataConverter]]
    """
    Класс конвертера данных (подкласс ``BaseDataConverter``); задаётся в наследнике.

    Конвертер превращает ``ParsedResult`` во view-model для Jinja2-шаблона страницы.
    Экземпляр создаётся в ``_make_converter()``.
    """

    def __init__(
        self,
        *,
        converter: BaseDataConverter | None = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует стратегию; ``include_passport_links`` игнорируется."""
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        kwargs.pop("include_passport_links", None)
        super().__init__(
            converter=converter or self._make_converter(),
            **kwargs,
        )

    @classmethod
    def _make_converter(cls, include_passport_links: bool = True) -> BaseDataConverter:
        """
        Создаёт конвертер данных — экземпляр класса ``CONVERTER_CLS``.

        ``CONVERTER_CLS`` — подкласс ``BaseDataConverter``, который задаёт наследник
        (например, ``KitFixedConverter`` у ``KitFixedPageStrategy``).

        Args:
            include_passport_links: Не используется. Параметр нужен только для
                совместимости с сигнатурой ``_make_converter()`` у остальных стратегий
                (``ReleasePageStrategy``, ``ProfileCentricPageStrategy``); у страниц
                комплекта для встраивания ссылок на паспорта нет.

        Returns:
            Новый экземпляр ``CONVERTER_CLS``.
        """
        return cls.CONVERTER_CLS()
