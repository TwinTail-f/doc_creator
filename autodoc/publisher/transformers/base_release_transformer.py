"""Abstract base class for release document transformers."""

from autodoc.publisher.transformers.passport_link_mixin import (
    PassportLinkMixin,
    _DEFAULT_PASSPORT_PATTERN,
)
from autodoc.publisher.transformers.base_data_transformer import BaseDataTransformer


class BaseReleaseTransformer(PassportLinkMixin, BaseDataTransformer):
    """
    Базовый класс трансформеров документации релиза.

    Наследует ``_passport_link()`` из ``PassportLinkMixin``.
    Конкретные виды реализуют ``transform()``.
    """

    def __init__(
        self,
        include_passport_links: bool = True,
        passport_page_pattern: str | None = None,
    ) -> None:
        """
        Args:
            include_passport_links: Добавлять ли ссылки на паспорта компонентов.
            passport_page_pattern: Шаблон URL паспорта с плейсхолдерами
                ``{component_name}`` и ``{release_version}``.
                По умолчанию используется ``_DEFAULT_PASSPORT_PATTERN``.
        """
        self._include_passport_links: bool = include_passport_links
        self._pattern: str | None = passport_page_pattern or _DEFAULT_PASSPORT_PATTERN
