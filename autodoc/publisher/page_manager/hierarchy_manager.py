"""Менеджер иерархии страниц Confluence."""

from autodoc.infrastructure.logger import logger
from autodoc.publisher.clients.protocols import IConfluenceClient

_COMPONENT_PAGE_BODY: str = "Автоматически созданная страница компонента"
_VERSION_PAGE_BODY: str = "Автоматически созданная страница версии"


class PageHierarchyManager:
    """
    Управляет деревом страниц Confluence.

    Обеспечивает существование цепочки страниц:
    ``Корень → Компонент → Версия → Документация``.
    Промежуточные страницы создаются автоматически при первом обращении.
    """

    def __init__(self, confluence_client: IConfluenceClient) -> None:
        """
        Args:
            confluence_client: Реализация ``IConfluenceClient``.
        """
        self._client: IConfluenceClient = confluence_client
        logger.debug("Инициализирован")

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
            PublishError: Если создание промежуточных страниц не удалось.
        """
        logger.debug(f"Иерархия для {component_name}@{release_version}")

        comp_page_id = self._client.get_or_create_page(
            space=space,
            title=component_name,
            parent_id=root_parent_id,
            body=_COMPONENT_PAGE_BODY,
        )

        version_title = f"{component_name} {release_version}"
        version_page_id = self._client.get_or_create_page(
            space=space,
            title=version_title,
            parent_id=comp_page_id,
            body=_VERSION_PAGE_BODY,
        )

        return version_page_id
