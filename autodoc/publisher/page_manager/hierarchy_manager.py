"""
Менеджер иерархии страниц Confluence.
"""
from autodoc.infrastructure.logger import logger


class PageHierarchyManager:
    """
    Управляет деревом страниц Confluence.

    Обеспечивает существование цепочки страниц:
    ``Корень → Компонент → Версия → Документация``.
    Промежуточные страницы создаются автоматически.
    """

    def __init__(self, confluence_client) -> None:
        """
        Args:
            confluence_client: Экземпляр ``ConfluenceClient``.
        """
        self._client = confluence_client
        logger.debug('PageHierarchyManager инициализирован')

    def ensure_hierarchy_exists(
        self,
        space: str,
        root_parent_id: str,
        component_name: str,
        release_version: str,
    ) -> str:
        """
        Обеспечивает существование иерархии и возвращает ID родительской страницы.

        Создаёт при необходимости страницы уровней:
        ``Компонент`` и ``Компонент Версия``.

        Args:
            space: Ключ Space в Confluence.
            root_parent_id: ID корневой страницы иерархии.
            component_name: Имя компонента.
            release_version: Версия релиза.

        Returns:
            ID страницы версии — родителя для страницы документации.

        Raises:
            PublishError: Если создание страниц не удалось.
        """
        logger.debug(
            f'PageHierarchyManager: обеспечиваем иерархию '
            f'{component_name}@{release_version}'
        )

        comp_page_id = self._client.get_or_create_page(
            space=space,
            title=component_name,
            parent_id=root_parent_id,
            body='Автоматически созданная страница компонента',
        )

        version_title = f'{component_name} {release_version}'
        version_page_id = self._client.get_or_create_page(
            space=space,
            title=version_title,
            parent_id=comp_page_id,
            body='Автоматически созданная страница версии',
        )

        return version_page_id

    @staticmethod
    def build_hierarchy_path(
        root_title: str,
        component_name: str,
        release_version: str,
    ) -> tuple:
        """
        Формирует заголовки страниц иерархии.

        Args:
            root_title: Заголовок корневой страницы.
            component_name: Имя компонента.
            release_version: Версия релиза.

        Returns:
            Кортеж ``(component_title, version_title, doc_title)``.
        """
        return (
            component_name,
            f'{component_name} {release_version}',
            f'Documentation {component_name} {release_version}',
        )
