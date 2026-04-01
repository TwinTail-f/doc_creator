"""Менеджер иерархии страниц Confluence."""
from autodoc.infrastructure.logger import logger
from autodoc.publisher.clients.confluence_client import ConfluenceClient

_COMPONENT_PAGE_BODY: str = 'Автоматически созданная страница компонента'
_VERSION_PAGE_BODY: str = 'Автоматически созданная страница версии'


class PageHierarchyManager:
    """
    Управляет деревом страниц Confluence.

    Обеспечивает существование цепочки страниц:
    ``Корень → Компонент → Версия → Документация``.
    Промежуточные страницы создаются автоматически при первом обращении.
    """

    def __init__(self, confluence_client: ConfluenceClient) -> None:
        """
        Args:
            confluence_client: Экземпляр ``ConfluenceClient``.
        """
        self._client: ConfluenceClient = confluence_client
        logger.debug('PageHierarchyManager инициализирован')

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
        logger.debug(
            'PageHierarchyManager: иерархия для %s@%s', component_name, release_version
        )

        comp_page_id = self._client.get_or_create_page(
            space=space,
            title=component_name,
            parent_id=root_parent_id,
            body=_COMPONENT_PAGE_BODY,
        )

        version_title = '%s %s' % (component_name, release_version)
        version_page_id = self._client.get_or_create_page(
            space=space,
            title=version_title,
            parent_id=comp_page_id,
            body=_VERSION_PAGE_BODY,
        )

        return version_page_id

    @staticmethod
    def build_hierarchy_path(
        root_title: str,
        component_name: str,
        release_version: str,
    ) -> tuple[str, str, str]:
        """
        Формирует заголовки страниц иерархии.

        Используется для предварительного вычисления заголовков без
        обращения к Confluence API, например в тестах или при валидации.

        Args:
            root_title: Заголовок корневой страницы (не используется
                        в результате, зарезервирован для расширений).
            component_name: Имя компонента.
            release_version: Версия релиза.

        Returns:
            Кортеж ``(component_title, version_title, doc_title)``.
        """
        return (
            component_name,
            '%s %s' % (component_name, release_version),
            'Documentation %s %s' % (component_name, release_version),
        )
