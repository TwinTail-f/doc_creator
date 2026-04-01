"""
Клиент Confluence REST API с retry-логикой и автоинкрементом версий страниц.
"""
from typing import Any

from atlassian import Confluence

from autodoc.config.schemas import ConfluenceConfigSchema
from autodoc.exceptions import PublishError
from autodoc.infrastructure.http_client import create_retryable_session
from autodoc.infrastructure.logger import logger
from autodoc.publisher.page_manager.version_manager import PageVersionManager

_DEFAULT_RETRY_COUNT: int = 3
_DEFAULT_BACKOFF_FACTOR: float = 1.0
_PAGE_TYPE: str = 'page'
_REPRESENTATION: str = 'storage'
_EXPAND_VERSION: str = 'version'
_INITIAL_VERSION: int = 1


class ConfluenceClient:
    """
    Клиент Confluence REST API с retry-логикой и автоинкрементом версий.

    Использует ``create_retryable_session`` из инфраструктуры вместо
    ручного создания ``Session`` + ``HTTPAdapter`` для устранения дублирования
    логики повторных попыток.
    """

    def __init__(self, config: ConfluenceConfigSchema) -> None:
        """
        Args:
            config: Валидированная конфигурация Confluence.

        Raises:
            PublishError: Если инициализация клиента не удалась.
        """
        try:
            self._timeout: int = config.confluence_request_timeout
            self._confluence = Confluence(
                url=config.url,
                username=config.username or '',
                password=config.token,
                verify_ssl=config.verify_ssl,
                cloud=config.cloud,
            )
            self._session = create_retryable_session(
                username=config.username or '',
                token=config.token,
                max_retries=_DEFAULT_RETRY_COUNT,
                backoff_factor=_DEFAULT_BACKOFF_FACTOR,
                timeout=config.confluence_request_timeout,
            )
            self._session.verify = config.verify_ssl
            logger.debug('ConfluenceClient инициализирован: %s', config.url)
        except Exception as e:
            raise PublishError('Ошибка инициализации ConfluenceClient: %s' % e) from e

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """
        Создаёт или обновляет страницу с автоинкрементом версии.

        Если страница с таким заголовком уже существует — обновляет её.
        Номер версии вычисляется через ``PageVersionManager``. При ошибке
        получения текущей версии используется версия 1 как безопасный fallback.

        Args:
            space: Ключ Space в Confluence.
            parent_id: ID родительской страницы.
            title: Заголовок страницы.
            body_html: HTML в Confluence Storage Format.

        Returns:
            Словарь с полями ``id``, ``version``, ``status``, ``message``.

        Raises:
            PublishError: Если публикация не удалась.
        """
        logger.info('публикация %r (Space: %s)', title, space)

        try:
            if self._confluence.page_exists(space=space, title=title):
                return self._update_existing_page(space, parent_id, title, body_html)
            return self._create_new_page(space, parent_id, title, body_html)

        except PublishError:
            raise
        except Exception as e:
            raise PublishError('Ошибка публикации страницы %r: %s' % (title, e)) from e

    def _update_existing_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """
        Обновляет существующую страницу Confluence.

        Получает текущий номер версии через ``PageVersionManager``. При
        ошибке получения версии использует ``_INITIAL_VERSION`` как fallback.

        Args:
            space: Ключ Space.
            parent_id: ID родительской страницы.
            title: Заголовок существующей страницы.
            body_html: Новое тело страницы.

        Returns:
            Словарь с полями ``id``, ``version``, ``status``, ``message``.
        """
        page_id = self._confluence.get_page_id(space=space, title=title)
        current_version: int = 0  # гарантирует определённость переменной до try-блока
        try:
            current_page = self.get_page(page_id)
            current_version = PageVersionManager.extract_version_from_response(current_page)
            next_version = PageVersionManager.get_next_version(current_version)
            PageVersionManager.log_version_update(title, current_version, next_version)
        except PublishError:
            next_version = _INITIAL_VERSION

        result = self._confluence.update_page(
            page_id=page_id,
            title=title,
            body=body_html,
            parent_id=parent_id,
            type=_PAGE_TYPE,
            representation=_REPRESENTATION,
            minor_edit=False,
        )
        logger.info('%r обновлена (ID: %s, версия: %d)', title, result.get('id'), next_version)
        return {
            'id': result.get('id'),
            'version': next_version,
            'status': 'updated',
            'message': 'Page updated to version %d' % next_version,
        }

    def _create_new_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """
        Создаёт новую страницу Confluence.

        Args:
            space: Ключ Space.
            parent_id: ID родительской страницы.
            title: Заголовок новой страницы.
            body_html: Тело страницы.

        Returns:
            Словарь с полями ``id``, ``version``, ``status``, ``message``.
        """
        result = self._confluence.create_page(
            space=space,
            title=title,
            body=body_html,
            parent_id=parent_id,
            type=_PAGE_TYPE,
            representation=_REPRESENTATION,
        )
        logger.info('%r создана (ID: %s)', title, result.get('id'))
        return {
            'id': result.get('id'),
            'version': _INITIAL_VERSION,
            'status': 'created',
            'message': 'Page created with version %d' % _INITIAL_VERSION,
        }

    def get_page_body(self, space: str, title: str) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

        Args:
            space: Ключ Space.
            title: Заголовок страницы.

        Returns:
            HTML-тело или пустая строка, если страница не найдена
            или произошла ошибка.
        """
        try:
            if self._confluence.page_exists(space=space, title=title):
                page = self._confluence.get_page_by_title(
                    space=space, title=title, expand='body.storage'
                )
                return page.get('body', {}).get('storage', {}).get('value', '')
        except Exception as e:
            logger.warning('не удалось получить тело %r: %s', title, e)
        return ''

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = '',
    ) -> str:
        """
        Находит страницу по заголовку или создаёт новую.

        Args:
            space: Ключ Space.
            title: Заголовок страницы.
            parent_id: ID родителя (обязателен при создании).
            body: Тело новой страницы. Если пустое — используется
                  заглушка-заголовок.

        Returns:
            ID страницы (строка).

        Raises:
            PublishError: Если страница не найдена и ``parent_id`` не передан,
                          либо при ошибке API.
        """
        try:
            if self._confluence.page_exists(space=space, title=title):
                return str(self._confluence.get_page_id(space=space, title=title))

            if not parent_id:
                raise PublishError(
                    'Невозможно создать страницу %r: не указан parent_id' % title
                )

            placeholder_body = body or '<p>Автоматически созданная страница: %s</p>' % title
            result = self._confluence.create_page(
                space=space,
                title=title,
                body=placeholder_body,
                parent_id=parent_id,
                type=_PAGE_TYPE,
                representation=_REPRESENTATION,
            )
            page_id = str(result.get('id', ''))
            logger.info('создана страница %r (ID: %s)', title, page_id)
            return page_id

        except PublishError:
            raise
        except Exception as e:
            raise PublishError(
                'Ошибка получения/создания страницы %r: %s' % (title, e)
            ) from e

    def get_page(
        self,
        page_id: str,
        expand: str | None = None,
    ) -> dict[str, Any]:
        """
        Загружает детали страницы по ID через REST API.

        Args:
            page_id: ID страницы.
            expand: Параметр ``expand`` запроса (например ``'version'``).
                    По умолчанию ``'version'``.

        Returns:
            Словарь с деталями страницы.

        Raises:
            PublishError: Если запрос завершился с ошибкой.
        """
        try:
            url = '%s/rest/api/content/%s' % (self._confluence.url, page_id)
            response = self._session.get(
                url,
                params={'expand': expand or _EXPAND_VERSION},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise PublishError('Ошибка получения страницы %s: %s' % (page_id, e)) from e
