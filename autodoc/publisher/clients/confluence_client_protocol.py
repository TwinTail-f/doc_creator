"""Протокол Confluence-клиента."""

from typing import Protocol

from autodoc.exceptions import ConfluenceError
from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.clients.models.page_result import PageResult

# Значения параметра `expand` Confluence REST API v1.
EXPAND_VERSION: str = "version"
EXPAND_BODY: str = "body.storage"
EXPAND_ANCESTORS: str = "ancestors"
EXPAND_VERSION_AND_ANCESTORS: str = f"{EXPAND_VERSION},{EXPAND_ANCESTORS}"
EXPAND_BODY_AND_ANCESTORS: str = f"{EXPAND_BODY},{EXPAND_ANCESTORS}"

class ConfluenceClientProtocol(Protocol):
    """Интерфейс Confluence-клиента для стратегий паблишера."""

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> ConfluencePage | None:
        """
        Ищет страницу по заголовку в указанном Space.

        Args:
            title:  Заголовок страницы.
            space:  Ключ Space. Если не указан — используется Space по умолчанию.
            expand: Параметр ``expand`` Confluence API (например ``EXPAND_VERSION``).

        Returns:
            ``ConfluencePage`` или ``None``, если страница не найдена.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """

    def get_page(self, page_id: str, expand: str = EXPAND_VERSION) -> ConfluencePage:
        """
        Загружает страницу по ID.

        Args:
            page_id: ID страницы.
            expand:  Параметр ``expand`` (по умолчанию ``EXPAND_VERSION``).

        Returns:
            ``ConfluencePage``.

        Raises:
            ConfluenceError: Если страница не найдена или запрос завершился ошибкой.
        """

    def get_page_body(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
    ) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

        Args:
            space:     Ключ Space.
            title:     Заголовок страницы.
            parent_id: Если указан — страница с тем же заголовком, но другим
                       предком, не будет возвращена.

        Returns:
            HTML-тело страницы или пустая строка, если страница не найдена.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """

    def ensure_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str = "",
    ) -> str:
        """
        Гарантирует наличие страницы с заголовком ``title`` под ``parent_id``.

        Args:
            space:     Ключ Space.
            parent_id: ID родительской страницы. Обязателен — у новой страницы
                       всегда есть родитель.
            title:     Заголовок страницы.
            body_html: Тело страницы при создании. Если пустое — вставляется
                       заглушка с заголовком страницы.

        Returns:
            ID страницы — существующей или только что созданной.

        Raises:
            ConfluenceError: Если создание страницы не удалось.
        """

    def publish_page(
        self,
        space: str,
        parent_id: str | None,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Публикует страницу: создаёт новую или обновляет существующую новой версией.

        Args:
            space:     Ключ Space в Confluence.
            parent_id: ID родительской страницы, либо ``None``/``""`` для
                       страницы верхнего уровня Space.
            title:     Заголовок страницы.
            body_html: Тело страницы в Confluence Storage Format (HTML).

        Returns:
            Результат операции в виде ``PageResult``.

        Raises:
            ConfluenceError: Если создание или обновление не удалось.
        """
