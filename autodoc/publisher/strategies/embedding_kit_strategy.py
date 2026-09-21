"""Общая база стратегий публикации страниц «комплекта для встраивания»."""

from typing import Any, ClassVar

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class EmbeddingKitPageStrategy(SinglePagePublishStrategy):
    """Базовая стратегия публикации страниц «комплекта для встраивания»."""

    DEFAULT_TEMPLATE: str = "embedding_kit.jinja2"
    CONVERTER_CLS: ClassVar[type[BaseDataConverter]]
    """Класс конвертера; задаётся в наследнике."""

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
        """Создаёт экземпляр ``CONVERTER_CLS``."""
        return cls.CONVERTER_CLS()
