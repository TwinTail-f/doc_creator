"""Стратегия публикации релизной документации на одной странице Confluence."""

from typing import Any

from autodoc.publisher.converters.base_data_converter import BaseDataConverter
from autodoc.publisher.converters.full_release_converter import FullReleaseConverter
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry
from autodoc.publisher.strategies.single_page_strategy import SinglePagePublishStrategy


class ReleasePageStrategy(SinglePagePublishStrategy, strategy_type="release"):
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
            converter: Конвертер данных. Если не передан, создаётся ``FullReleaseConverter``.
            **kwargs: Остальные параметры для ``SinglePagePublishStrategy``.
        """
        kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)
        kwargs.setdefault("link_injector", PassportPageRegistry.inject_links)
        super().__init__(
            converter=converter or self._make_converter(
                {"include_passport_links": kwargs.get("include_passport_links", True)}
            ),
            **kwargs,
        )

    @staticmethod
    def _make_converter(kwargs: dict[str, Any]) -> BaseDataConverter:
        """
        Создаёт ``FullReleaseConverter`` из аргументов конструктора.

        Args:
            kwargs: Словарь с ключом ``include_passport_links``.

        Returns:
            Готовый ``FullReleaseConverter``.
        """
        return FullReleaseConverter(
            include_passport_links=kwargs.get("include_passport_links", True),
        )
