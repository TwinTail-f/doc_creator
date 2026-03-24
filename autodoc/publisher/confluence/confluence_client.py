"""
Confluence REST API client с retry-логикой и автоинкрементом версий страниц.
"""
from typing import Any, Dict, Optional

import requests
from atlassian import Confluence
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from autodoc.config.schemas import ConfluenceConfigSchema
from autodoc.exceptions import PublishError
from autodoc.infrastructure.http_client import create_retryable_session  # 1.3
from autodoc.infrastructure.logger import logger


def _retry_on_network_error(func):
    """
    Декоратор автоматического retry при сетевых ошибках.

    3 попытки, exponential backoff 1–8 с, на ``Timeout`` и ``ConnectionError``.
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(
            (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
        ),
        reraise=True,
    )
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


class ConfluenceClient:
    """
    Клиент Confluence REST API с retry-логикой и автоинкрементом версий.

    1.3 Использует ``create_retryable_session`` из инфраструктуры —
    без дублирования логики retry.
    """

    def __init__(self, config: ConfluenceConfigSchema) -> None:
        """
        Args:
            config: Валидированная конфигурация Confluence.

        Raises:
            PublishError: Если инициализация клиента не удалась.
        """
        try:
            self._timeout = config.confluence_request_timeout
            self._verify_ssl = config.verify_ssl

            self._confluence = Confluence(
                url=config.url,
                username=config.username or '',
                password=config.token,
                verify_ssl=config.verify_ssl,
                cloud=config.cloud,
            )

            # 1.3 Заменяем ручное создание Session+HTTPAdapter на create_retryable_session
            self._session = create_retryable_session(
                username=config.username or '',
                token=config.token,
                max_retries=3,
                backoff_factor=1.0,
                timeout=config.confluence_request_timeout,
            )
            self._session.verify = config.verify_ssl

            logger.debug('ConfluenceClient инициализирован: %s', config.url)
        except Exception as e:
            raise PublishError('Ошибка инициализации ConfluenceClient: %s' % e) from e

    @_retry_on_network_error
    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> Dict[str, Any]:
        """
        Создаёт или обновляет страницу с автоинкрементом версии.

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
        logger.info('ConfluenceClient: публикация %r (Space: %s)', title, space)

        try:
            if self._confluence.page_exists(space=space, title=title):
                page_id = self._confluence.get_page_id(space=space, title=title)
                try:
                    current_page = self.get_page(page_id)
                    current_version = current_page.get('version', {}).get('number', 1)
                    next_version = current_version + 1
                except PublishError:
                    next_version = 1

                result = self._confluence.update_page(
                    page_id=page_id,
                    title=title,
                    body=body_html,
                    parent_id=parent_id,
                    type='page',
                    representation='storage',
                    minor_edit=False,
                )
                logger.info(
                    'ConfluenceClient: %r обновлена (ID: %s, версия: %d)',
                    title, result.get('id'), next_version,
                )
                return {
                    'id': result.get('id'),
                    'version': next_version,
                    'status': 'updated',
                    'message': 'Page updated to version %d' % next_version,
                }

            result = self._confluence.create_page(
                space=space,
                title=title,
                body=body_html,
                parent_id=parent_id,
                type='page',
                representation='storage',
            )
            logger.info('ConfluenceClient: %r создана (ID: %s)', title, result.get('id'))
            return {
                'id': result.get('id'),
                'version': 1,
                'status': 'created',
                'message': 'Page created with version 1',
            }

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise
        except Exception as e:
            raise PublishError('Ошибка публикации страницы %r: %s' % (title, e)) from e

    @_retry_on_network_error
    def get_page_body(self, space: str, title: str) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

        Args:
            space: Ключ Space.
            title: Заголовок страницы.

        Returns:
            HTML или пустая строка.
        """
        try:
            if self._confluence.page_exists(space=space, title=title):
                page = self._confluence.get_page_by_title(
                    space=space, title=title, expand='body.storage'
                )
                return page.get('body', {}).get('storage', {}).get('value', '')
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise
        except Exception as e:
            logger.warning('ConfluenceClient: не удалось получить тело %r: %s', title, e)
        return ''

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: Optional[str] = None,
        body: str = '',
    ) -> str:
        """
        Находит страницу или создаёт её.

        Args:
            space: Ключ Space.
            title: Заголовок.
            parent_id: ID родителя (обязателен при создании).
            body: Тело при создании.

        Returns:
            ID страницы.

        Raises:
            PublishError: Если операция не удалась.
        """
        try:
            if self._confluence.page_exists(space=space, title=title):
                return str(self._confluence.get_page_id(space=space, title=title))

            if not parent_id:
                raise PublishError(
                    'Невозможно создать страницу %r: не указан parent_id' % title
                )

            result = self._confluence.create_page(
                space=space,
                title=title,
                body=body or '<p>Автоматически созданная страница: %s</p>' % title,
                parent_id=parent_id,
                type='page',
                representation='storage',
            )
            page_id = str(result.get('id', ''))
            logger.info('ConfluenceClient: создана страница %r (ID: %s)', title, page_id)
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
        expand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Загружает детали страницы по ID.

        Args:
            page_id: ID страницы.
            expand: Параметр expand (например ``'version'``).

        Returns:
            Словарь с деталями страницы.

        Raises:
            PublishError: Если запрос не удался.
        """
        try:
            url = '%s/rest/api/content/%s' % (self._confluence.url, page_id)
            response = self._session.get(
                url,
                params={'expand': expand or 'version'},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise PublishError('Ошибка получения страницы %s: %s' % (page_id, e)) from e
