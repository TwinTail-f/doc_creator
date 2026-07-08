"""Менеджер иерархии страниц Confluence."""

from autodoc.common.logger import logger
from autodoc.exceptions import ConfluenceError
from autodoc.publisher.clients.confluence_client import ConfluenceClient

_CHILDREN_MACRO_ID: str = "8cb4ae85-0212-4b3d-a15f-77899af1f1d7"


def _build_children_body(intro_text: str, depth: int) -> str:
    """Формирует тело страницы в Confluence Storage Format для автоматически создаваемой страницы иерархии."""
    return (
        f"{intro_text}"
        "<p>"
        f'<ac:structured-macro ac:macro-id="{_CHILDREN_MACRO_ID}" '
        'ac:name="children" ac:schema-version="2">'
        f'<ac:parameter ac:name="depth">{depth}</ac:parameter>'
        "</ac:structured-macro>"
        "</p>"
    )


_COMPONENT_PAGE_BODY: str = _build_children_body(
    "Автоматически созданная страница компонента", depth=3
)
_VERSION_PAGE_BODY: str = _build_children_body(
    "Автоматически созданная страница версии компонента", depth=2
)


class PageHierarchyManager:
    """
    Управляет деревом страниц Confluence.

    Обеспечивает существование цепочки страниц:
    ``Корень → Компонент → Версия → Документация``.
    Промежуточные страницы создаются автоматически при первом обращении.
    Если промежуточная страница уже существует, но под другим родителем,
    поведение определяется ``title_conflict_policy`` конфигурации Confluence
    (см. ``ConfluenceClient.resolve_existing_page_id`` и
    ``ConfluenceClient.create_page``).
    """

    def __init__(self, confluence_client: ConfluenceClient) -> None:
        """
        Создаёт менеджер иерархии с переданным клиентом Confluence.

        Args:
            confluence_client: Клиент Confluence, используемый для чтения
                               и публикации страниц.
        """
        self._client: ConfluenceClient = confluence_client
        logger.debug(
            f"{self.__class__.__name__} инициализирован "
            f"(client={confluence_client.__class__.__name__})"
        )

    def ensure_hierarchy_exists(
        self,
        space: str,
        root_parent_id: str,
        component_name: str,
        release_version: str,
    ) -> str:
        """
        Обеспечивает существование иерархии и возвращает ID страницы версии.

        Создаёт при необходимости страницы уровней ``Компонент`` и
        ``Компонент Версия``. Обе операции идемпотентны: если страница
        уже существует, возвращается её ID без создания дубликата.

        Args:
            space: Ключ Space в Confluence.
            root_parent_id: ID корневой страницы иерархии.
            component_name: Имя компонента (используется как заголовок страницы).
            release_version: Версия релиза (добавляется к имени компонента).

        Returns:
            ID страницы версии — она становится родителем для страницы паспорта.

        Raises:
            ConfluenceError: Если создание промежуточных страниц не удалось.
        """
        logger.debug(f"Иерархия для {component_name}@{release_version}")

        comp_page_id = self._get_or_create_page_id(
            space=space,
            parent_id=root_parent_id,
            title=component_name,
            body_html=_COMPONENT_PAGE_BODY,
        )

        version_title = f"{component_name} {release_version}"
        version_page_id = self._get_or_create_page_id(
            space=space,
            parent_id=comp_page_id,
            title=version_title,
            body_html=_VERSION_PAGE_BODY,
        )

        return version_page_id

    def _get_or_create_page_id(
        self, space: str, parent_id: str, title: str, body_html: str
    ) -> str:
        """
        Возвращает ID страницы с заданным заголовком, создавая её при отсутствии.

        Args:
            space: Ключ Space.
            parent_id: Родитель, под которым должна находиться страница.
            title: Заголовок страницы.
            body_html: Тело страницы, используемое только при создании.

        Returns:
            ID существующей (на месте или перенесённой) либо только что
            созданной страницы.

        Raises:
            ConfluenceError: Если поиск, перенос или создание страницы
                              завершились ошибкой.
        """
        page_id = self._resolve_existing_page_id(space=space, parent_id=parent_id, title=title)
        if page_id is not None:
            return page_id
        return self._create_page(space=space, parent_id=parent_id, title=title, body_html=body_html)

    def _resolve_existing_page_id(self, *, space: str, parent_id: str, title: str) -> str | None:
        """
        Ищет уже существующую страницу с заданным заголовком под указанным родителем.

        Args:
            space: Ключ Space.
            parent_id: Родитель, под которым должна находиться страница.
            title: Заголовок страницы.

        Returns:
            ID найденной страницы либо ``None``, если она ещё не существует.

        Raises:
            ConfluenceError: Если поиск или перенос существующей страницы
                              под ожидаемого родителя завершились ошибкой.
        """
        try:
            return self._client.resolve_existing_page_id(
                space=space, parent_id=parent_id, title=title
            )
        except ConfluenceError:
            logger.error(f"Не удалось найти существующую страницу {title!r} (parent_id={parent_id})")
            raise

    def _create_page(self, *, space: str, parent_id: str, title: str, body_html: str) -> str:
        """
        Создаёт страницу с заданным заголовком под указанным родителем.

        Args:
            space: Ключ Space.
            parent_id: Родитель, под которым должна находиться страница.
            title: Заголовок страницы.
            body_html: Тело создаваемой страницы.

        Returns:
            ID только что созданной страницы.

        Raises:
            ConfluenceError: Если создание страницы завершилось ошибкой.
        """
        try:
            result = self._client.create_page(
                space=space, parent_id=parent_id, title=title, body_html=body_html
            )
            return result.id
        except ConfluenceError:
            logger.error(f"Не удалось создать страницу {title!r} (parent_id={parent_id})")
            raise
