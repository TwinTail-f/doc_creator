"""
Протокол (структурный интерфейс) Confluence-клиента, используемого стратегиями паблишера.
"""

from typing import Any, Protocol, TypedDict


class PageResult(TypedDict):
    """Результат операции создания или обновления страницы Confluence."""

    id: str
    """ID страницы в Confluence."""

    version: int
    """Актуальный номер версии после операции."""

    status: str
    """``'created'`` при создании, ``'updated'`` при обновлении."""

    message: str
    """Читаемое описание результата для логирования."""


class ConfluenceClientProtocol(Protocol):
    """Интерфейс Confluence-клиента для стратегий паблишера."""

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Публикует страницу в Confluence: создаёт новую или обновляет существующую.

        Args:
            space:     Ключ Space в Confluence.
            parent_id: ID родительской страницы.
            title:     Заголовок страницы.
            body_html: Тело страницы в Confluence Storage Format.

        Returns:
            Результат операции в виде ``PageResult``.

        Raises:
            ConfluenceError: Если создание или обновление завершилось ошибкой.
        """

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = "",
    ) -> str:
        """
        Возвращает ID существующей страницы или создаёт новую.

        Args:
            space:     Ключ Space.
            title:     Заголовок страницы.
            parent_id: ID родительской страницы. Обязателен при создании новой страницы.
            body:      Тело новой страницы. Если пустое — вставляется заглушка.

        Returns:
            ID страницы в виде строки.

        Raises:
            ConfluenceError: Если страница не найдена и ``parent_id`` не указан,
                             либо если запрос к API завершился ошибкой.
        """

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> dict[str, Any] | None:
        """
        Ищет страницу по заголовку в указанном Space.

        Args:
            title:  Заголовок страницы.
            space:  Ключ Space. Если не указан — используется пространство по умолчанию.
            expand: Параметр ``expand`` для Confluence API
                    (например ``'version'`` или ``'body.storage'``).

        Returns:
            Словарь с данными страницы или ``None``, если страница не найдена.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """

    def get_page(
        self,
        page_id: str,
        expand: str = "",
    ) -> dict[str, Any]:
        """
        Загружает страницу по ID.

        Args:
            page_id: ID страницы.
            expand:  Параметр ``expand`` для Confluence API (например ``'version'``).

        Returns:
            Словарь с данными страницы.

        Raises:
            ConfluenceError: Если страница не найдена или запрос завершился ошибкой.
        """

    def get_page_body(self, space: str, title: str) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

        Args:
            space: Ключ Space.
            title: Заголовок страницы.

        Returns:
            HTML-тело страницы или пустая строка, если страница не найдена.
        """