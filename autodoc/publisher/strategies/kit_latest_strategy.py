"""Стратегия публикации страницы «Встраивание последних версий компонентов»."""

from typing import ClassVar

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.kit_latest_converter import KitLatestConverter
from autodoc.publisher.strategies.embedding_kit_strategy import EmbeddingKitPageStrategy


class KitLatestPageStrategy(EmbeddingKitPageStrategy):
    """Публикует список ссылок на последние сборки компонентов по каналам."""

    CONVERTER_CLS: ClassVar[type[BaseDataConverter]] = KitLatestConverter
