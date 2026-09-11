"""Стратегия публикации релизной документации на одной странице Confluence."""

from typing import Any

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.component_centric_converter import ComponentCentricConverter
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class ReleasePageStrategy(SinglePagePublishStrategy):
    """
    Публикует документацию релиза (вид от компонентов) на одной странице Confluence.

    Опционально вставляет ссылки на индивидуальные паспорта компонентов,
    если файл ``passport_pages.json`` был создан предшествующим запуском
    ``PassportsStrategy``.
    """

    DEFAULT_TEMPLATE: str = "release_doc.jinja2"

    def __init__(
        self,
        *,
        converter: BaseDataConverter | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Инициализирует стратегию публикации документации релиза.

        Args:
            converter: Конвертер данных. Если не передан, создаётся ``ComponentCentricConverter``.
            **kwargs: Остальные параметры для ``SinglePagePublishStrategy``.
                ``include_passport_links``, если передан, потребляется здесь и
                уходит в конструктор конвертера — сама стратегия об этом флаге
                ничего не знает (см. ``ComponentCentricConverter.enrich_with_passport_links``).
        """
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        include_passport_links = kwargs.pop("include_passport_links", True)
        super().__init__(
            converter=converter or self._make_converter(include_passport_links),
            **kwargs,
        )

    @staticmethod
    def _make_converter(include_passport_links: bool = True) -> BaseDataConverter:
        """
        Создаёт ``ComponentCentricConverter`` из аргументов конструктора.

        Args:
            include_passport_links: Включать ли ссылки на паспорта компонентов.

        Returns:
            Готовый ``ComponentCentricConverter``.
        """
        return ComponentCentricConverter(include_passport_links=include_passport_links)
