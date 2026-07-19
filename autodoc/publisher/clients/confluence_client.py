"""Клиент Confluence REST API v1."""

from typing import Any, Literal

from autodoc.publisher.clients.confluence_transport import ConfluenceTransport
from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.clients.models.page_result import PageResult

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError
from autodoc.common.logger import logger

_PAGE_TYPE: str = "page"
_STORAGE_REPRESENTATION: str = "storage"
_INITIAL_VERSION: int = 1

# Значения параметра `expand` Confluence REST API v1.
EXPAND_VERSION: str = "version"
EXPAND_BODY: str = "body.storage"
EXPAND_ANCESTORS: str = "ancestors"
EXPAND_VERSION_AND_ANCESTORS: str = f"{EXPAND_VERSION},{EXPAND_ANCESTORS}"
EXPAND_BODY_AND_ANCESTORS: str = f"{EXPAND_BODY},{EXPAND_ANCESTORS}"
EXPAND_VERSION_BODY_ANCESTORS: str = f"{EXPAND_VERSION},{EXPAND_BODY},{EXPAND_ANCESTORS}"


class ConfluenceClient:
    """Клиент для публикации и чтения страниц Confluence через REST API v1."""

    def __init__(self, config: ConfluenceConfigSchema) -> None:
        """
        Создаёт клиент, готовый к работе с Confluence.

        Args:
            config: Валидированная конфигурация с URL, токеном и параметрами SSL.
        """
        self._space: str = config.space
        self._title_conflict_policy: Literal["error", "move"] = config.title_conflict_policy
        self._transport: ConfluenceTransport = ConfluenceTransport(config)
        logger.debug(
            f"Инициализирован (space={self._space}, title_conflict_policy={self._title_conflict_policy})"
        )

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> ConfluencePage | None:
        """
        Ищет страницу по заголовку в указанном Space.

        Args:
            title: Заголовок страницы.
            space: Ключ Space. Если не указан — используется Space по умолчанию.
            expand: Параметр ``expand`` Confluence API.

        Returns:
            ``ConfluencePage`` или ``None``, если страница не найдена.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """
        params: dict[str, str] = {
            "spaceKey": space or self._space,
            "title": title,
            "type": _PAGE_TYPE,
        }
        if expand:
            params["expand"] = expand

        try:
            results = self._transport.search_content(params)
        except ConfluenceError:
            logger.error(f"Ошибка при поиске страницы {title!r} (space={space or self._space})")
            raise
        return ConfluencePage.from_api(results[0]) if results else None

    def get_page(self, page_id: str, expand: str = EXPAND_VERSION) -> ConfluencePage:
        """
        Загружает страницу по идентификатору.

        Args:
            page_id: ID страницы.
            expand: Параметр ``expand`` (по умолчанию ``EXPAND_VERSION``).

        Returns:
            ``ConfluencePage``.

        Raises:
            ConfluenceError: Если страница не найдена или запрос завершился ошибкой.
        """
        try:
            data = self._transport.get_content(page_id, expand)
        except ConfluenceError:
            logger.error(f"Ошибка при получении страницы (ID={page_id})")
            raise
        return ConfluencePage.from_api(data)

    def get_page_body(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
    ) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

        Args:
            space:  Ключ Space.
            title: Заголовок страницы.
            parent_id: Если указан — поиск выполняется с проверкой принадлежности
                       дереву: страница с тем же заголовком, но другим предком,
                       не будет возвращена.

        Returns:
            HTML-тело страницы или пустая строка, если страница не найдена.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """
        if parent_id:
            page = self._find_page_in_subtree(
                title, space, parent_id, expand=EXPAND_BODY_AND_ANCESTORS
            )
        else:
            page = self.find_page(title, space=space, expand=EXPAND_BODY)
        return page.body_html if page else ""

    def resolve_existing_page_id(self, space: str, parent_id: str, title: str) -> str | None:
        """
        Возвращает ID существующей страницы с заданным заголовком, если она есть.

        Если страница с этим заголовком найдена под другим родителем, конфликт
        разрешается согласно ``title_conflict_policy`` конфигурации (перенос
        или исключение) — см. ``_resolve_title_conflict``. Страница никогда не
        создаётся этим методом.

        Args:
            space: Ключ Space.
            parent_id: Ожидаемый родитель страницы.
            title: Заголовок страницы.

        Returns:
            ID страницы (на прежнем месте или перенесённой), либо ``None``,
            если страницы с таким заголовком не существует ни в одном поддереве.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой, либо
                              обнаружен конфликт заголовков при
                              ``title_conflict_policy == "error"``.
        """
        existing = self.find_page(title, space=space, expand=EXPAND_VERSION_AND_ANCESTORS)
        if not existing:
            return None
        if not parent_id or existing.is_descendant_of(parent_id):
            return existing.id
        try:
            moved = self._resolve_title_conflict(existing, parent_id, title, body_html=None)
        except ConfluenceError:
            logger.error(f"Ошибка при переносе страницы {title!r} (parent_id={parent_id})")
            raise
        return moved.id

    def publish_page(
        self,
        space: str,
        parent_id: str | None,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Публикует страницу: создаёт новую или обновляет существующую новой версией.

        Если страница с тем же заголовком найдена под другим родителем — поведение
        определяется ``title_conflict_policy`` конфигурации: при ``'error'`` операция
        прерывается исключением, при ``'move'`` — страница переносится под ожидаемого
        родителя и публикуется с переданным ``body_html``.

        Args:
            space:     Ключ Space.
            parent_id: ID родительской страницы или ``None`` для страницы без родителя.
            title:     Заголовок страницы.
            body_html: Тело страницы в Confluence Storage Format.

        Returns:
            Результат операции в виде ``PageResult``.

        Raises:
            ConfluenceError: Если создание или обновление не удалось, либо обнаружен
                              конфликт заголовков при ``title_conflict_policy == "error"``.
        """
        logger.info(f"Публикация страницы {title} (space={space})")

        existing = self.find_page(title, space=space, expand=EXPAND_VERSION_AND_ANCESTORS)
        if not existing:
            return self.create_page(space, parent_id, title, body_html)
        try:
            if not parent_id or existing.is_descendant_of(parent_id):
                return self._update_page(existing, parent_id, title, body_html)
            return self._resolve_title_conflict(existing, parent_id, title, body_html)
        except ConfluenceError:
            logger.error(f"Ошибка при публикации страницы {title!r} (space={space})")
            raise

    def _find_page_in_subtree(
        self,
        title: str,
        space: str,
        parent_id: str | None,
        expand: str = EXPAND_ANCESTORS,
    ) -> ConfluencePage | None:
        """
        Ищет страницу по заголовку и проверяет принадлежность дереву ``parent_id``.

        Если ``parent_id`` не задан — проверка принадлежности дереву пропускается.

        Используется только для чтения тела страницы (``get_page_body``): не
        создаёт и не изменяет страницы, при конфликте просто возвращает ``None``.

        Args:
            title: Заголовок страницы.
            space: Ключ Space.
            parent_id: Ожидаемый родитель, либо ``None``/``""``.
            expand: Параметр ``expand`` — должен включать ``ancestors``.

        Returns:
            ``ConfluencePage`` или ``None``, если страница не найдена либо
            найдена в другом поддереве.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """
        existing = self.find_page(title, space=space, expand=expand)
        if existing and parent_id and not existing.is_descendant_of(parent_id):
            logger.warning(
                f"Страница {title!r} найдена в другом дереве "
                f"(ожидаемый parent_id={parent_id}), тело страницы не будет возвращено."
            )
            return None
        return existing

    def _resolve_title_conflict(
        self,
        existing_elsewhere: ConfluencePage,
        parent_id: str,
        title: str,
        body_html: str | None,
    ) -> PageResult:
        """
        Разрешает конфликт заголовка согласно ``title_conflict_policy``.

        Вызывается, когда страница с заданным заголовком найдена, но не под
        ожидаемым родителем. Создание новой страницы с тем же заголовком
        невозможно — Confluence требует уникальности заголовков в пределах Space.

        Args:
            existing_elsewhere: Найденная страница с совпадающим заголовком в другом поддереве.
            parent_id: Ожидаемый родитель.
            title: Заголовок страницы.
            body_html: Новое тело для переноса, либо ``None`` — тогда сохраняется
                       текущее тело найденной страницы.

        Returns:
            Результат переноса страницы под ожидаемого родителя.

        Raises:
            ConfluenceError: Если ``title_conflict_policy == "error"``, либо перенос не удался.
        """
        if self._title_conflict_policy == "error":
            parent_hint = (
                existing_elsewhere.ancestor_ids[-1] if existing_elsewhere.ancestor_ids else "?"
            )
            raise ConfluenceError(
                f"Страница {title!r} уже существует в Space {self._space!r} "
                f"(ID={existing_elsewhere.id}, текущий родитель={parent_hint}), "
                f"но не под ожидаемым parent_id={parent_id!r}. Перенесите страницу "
                "вручную либо включите title_conflict_policy='move' в конфигурации Confluence."
            )

        if body_html is None:
            existing_elsewhere = self.get_page(
                existing_elsewhere.id, expand=EXPAND_VERSION_BODY_ANCESTORS
            )
            body_html = existing_elsewhere.body_html

        logger.warning(
            f"Перенос страницы {title!r} (ID={existing_elsewhere.id}) под parent_id={parent_id!r} "
            "(title_conflict_policy='move')"
        )
        return self._update_page(existing_elsewhere, parent_id, title, body_html)

    def create_page(
        self,
        space: str,
        parent_id: str | None,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Создаёт новую страницу в Confluence и возвращает результат операции.

        Args:
            space: Ключ Space.
            parent_id: ID родительской страницы или ``None``.
            title: Заголовок создаваемой страницы.
            body_html: Тело страницы в Confluence Storage Format.

        Returns:
            ``PageResult`` с ID, версией и статусом созданной страницы.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """
        payload = self._build_payload(
            title=title,
            body_html=body_html,
            version_number=_INITIAL_VERSION,
            parent_id=parent_id,
            space=space,
        )
        try:
            data = self._transport.create_content(payload, title)
        except ConfluenceError:
            logger.error(f"Ошибка при создании страницы {title!r} (parent_id={parent_id})")
            raise

        page_id = str(data.get("id", ""))
        logger.info(f"Создана страница {title} (ID: {page_id})")
        return PageResult(
            id=page_id,
            version=_INITIAL_VERSION,
            status="created",
            message=f"Страница создана с версией {_INITIAL_VERSION}",
        )

    def _update_page(
        self,
        existing_page: ConfluencePage,
        parent_id: str | None,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Обновляет тело и версию существующей страницы в Confluence.

        Args:
            existing_page: Текущее состояние страницы для получения версии и ID.
            parent_id: ID родительской страницы или ``None``.
            title: Заголовок страницы.
            body_html: Новое тело страницы в Confluence Storage Format.

        Returns:
            ``PageResult`` с ID, новой версией и статусом ``'updated'``.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
        """
        next_version = existing_page.version + 1
        logger.info(
            f"Обновление {title}: v{existing_page.version} → v{next_version} "
            f"(ID: {existing_page.id})"
        )

        payload = self._build_payload(
            title=title,
            body_html=body_html,
            version_number=next_version,
            parent_id=parent_id,
            space=None,
        )
        self._transport.update_content(existing_page.id, payload, title)

        return PageResult(
            id=existing_page.id,
            version=next_version,
            status="updated",
            message=f"Страница обновлена до версии {next_version}",
        )

    @staticmethod
    def _build_payload(
        title: str,
        body_html: str,
        version_number: int,
        parent_id: str | None,
        space: str | None = None,
    ) -> dict[str, Any]:
        """
        Формирует тело запроса для создания или обновления страницы.

        Args:
            title: Заголовок страницы.
            body_html: Тело в Storage Format.
            version_number: Номер версии (при обновлении — следующая версия).
            parent_id: ID родительской страницы, либо ``None``/``""``.
            space: Ключ Space. Передаётся только при создании.

        Returns:
            Словарь, готовый для сериализации в JSON.
        """
        payload: dict[str, Any] = {
            "type": _PAGE_TYPE,
            "title": title,
            "version": {"number": version_number},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": _STORAGE_REPRESENTATION,
                }
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        if space:
            payload["space"] = {"key": space}
        return payload
