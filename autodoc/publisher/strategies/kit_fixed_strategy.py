"""Стратегия публикации страницы «Комплект для встраивания компонентов platform»."""

from typing import ClassVar

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.kit_fixed_converter import KitFixedConverter
from autodoc.publisher.strategies.embedding_kit_strategy import EmbeddingKitPageStrategy


class KitFixedPageStrategy(EmbeddingKitPageStrategy):
    """
    Публикует список фиксированных версий компонентов платформы по каналам.

    См. докстринг ``EmbeddingKitPageStrategy`` — здесь задан только конвертер.
    """

    CONVERTER_CLS: ClassVar[type[BaseDataConverter]] = KitFixedConverter
