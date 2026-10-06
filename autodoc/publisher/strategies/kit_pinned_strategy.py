"""Стратегия публикации страницы «Комплект для встраивания компонентов platform»."""

from typing import ClassVar

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.kit_pinned_converter import KitPinnedConverter
from autodoc.publisher.strategies.embedding_kit_strategy import EmbeddingKitPageStrategy


class KitPinnedPageStrategy(EmbeddingKitPageStrategy):
    """Публикует список закреплённых версий компонентов по каналам."""

    CONVERTER_CLS: ClassVar[type[BaseDataConverter]] = KitPinnedConverter
