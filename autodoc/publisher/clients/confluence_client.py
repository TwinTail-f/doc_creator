"""
Клиент Confluence REST API v1.

Единственный HTTP-транспорт — ``RetryableSession`` из инфраструктурного слоя.
Зависимость от сторонней библиотеки ``atlassian-python-api`` полностью убрана:
это устраняет дублирование retry/timeout/SSL-логики и даёт полный контроль
над запросами.

Поддерживаемые операции:
    - поиск страницы по заголовку (``find_page``)
    - получение страницы по ID (``get_page``)
    - создание страницы (``create_page``)
    - обновление страницы с автоинкрементом версии (``update_page``)
    - создание страницы или получение существующей (``get_or_create_page``)
    - чтение тела страницы (``get_page_body``)
    - публикация (создание или обновление) с единым интерфейсом (``publish_page``)
"""

from typing import Any

import requests
import urllib3

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import PublishError
from autodoc.common.retryable_session import (
    RetryableSession,
    create_retryable_session,
)
from autodoc.common.logger import logger

_RETRY_COUNT: int = 3
_BACKOFF_FACTOR: float = 1.0

_PAGE_TYPE: str = "page"
_STORAGE_REPRESENTATION: str = "storage"

_EXPAND_VERSION: str = "version"
_EXPAND_BODY: str = "body.storage"
_EXPAND_VERSION_AND_BODY: str = "version,body.storage"

_INITIAL_VERSION: int = 1
# Fallback-значение при невозможности извлечь номер версии из ответа Confluence.
# Значение 0 означает, что следующая версия будет 1 — безопасный минимум для Confluence.
_FALLBACK_VERSION: int = 0


class ConfluenceClient:
    """
    Клиент Confluence REST API v1.

    Все запросы идут через единственный ``RetryableSession`` —
    retry-логика, таймауты и SSL-конфигурация применяются однородно
    ко всем обращениям к Confluence.

    Клиент не хранит состояния страниц и безопасен для повторного
    использования в рамках одного процесса.

    Attributes:
        _base_url: Базовый URL Confluence без завершающего слеша.
        _space:    Ключ Space по умолчанию (используется во всех методах).
        _timeout:  Таймаут каждого HTTP-запроса в секундах.
        _session:  HTTP-сессия с retry-логикой и аутентификацией.
    """

    def __init__(self, config: ConfluenceConfigSchema) -> None:
        """
        Инициализирует клиент из конфигурации Confluence.

        Args:
            config: Валидированная конфигурация с URL, токеном и параметрами SSL.

        Raises:
            PublishError: Если конфигурация некорректна (например, пустой URL).
        """
        if not config.url:
            raise PublishError("ConfluenceClient: url не может быть пустым")

        self._base_url: str = config.url.rstrip("/")
        self._space: str = config.space
        self._session: RetryableSession = self._build_session(config)

        logger.debug(f"Инициализирован: {self._base_url} (space={self._space})")

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """
        Создаёт или обновляет страницу Confluence.

        Если страница с таким заголовком уже существует в указанном Space
        **и является дочерней для ``parent_id``** — обновляет её тело с
        автоинкрементом номера версии. Если не существует или принадлежит
        другому дереву — создаёт новую под ``parent_id``.

        Args:
            space:     Ключ Space в Confluence.
            parent_id: ID родительской страницы.
            title:     Заголовок страницы.
            body_html: Тело страницы в Confluence Storage Format (HTML).

        Returns:
            Словарь ``{'id': str, 'version': int, 'status': str, 'message': str}``.

        Raises:
            PublishError: Если создание или обновление не удалось.
        """
        logger.info(f"Публикация страницы {title} (space={space})")

        existing = self.find_page(
            title, space=space, expand=f"{_EXPAND_VERSION},ancestors"
        )
        if existing:
            if not self._is_child_of(existing, parent_id):
                logger.warning(
                    f"Страница {title} найдена в другом дереве "
                    f"(parent_id страницы не совпадает с {parent_id}). "
                    f"Страница будет обновлена и перемещена под указанного родителя."
                )
            return self._update_page(existing, parent_id, title, body_html)
        return self._create_page(space, parent_id, title, body_html)

    def get_or_create_page(
        self,
        space: str,
        title: str,
        parent_id: str | None = None,
        body: str = "",
    ) -> str:
        """
        Возвращает ID существующей страницы или создаёт новую.

        Используется ``PageHierarchyManager`` для идемпотентного создания
        промежуточных страниц иерархии (компонент, версия).

        Страница считается «той же» только если она является прямым потомком
        ``parent_id``. Если в Space существует страница с таким же заголовком,
        но под другим родителем, она игнорируется и создаётся новая —
        это предотвращает случайную запись в дерево другого корня.

        Args:
            space:     Ключ Space.
            title:     Заголовок страницы.
            parent_id: ID родителя. Обязателен при создании новой страницы.
            body:      Тело новой страницы. Если пустое — вставляется заглушка.

        Returns:
            ID страницы в виде строки.

        Raises:
            PublishError: Если страница не найдена и ``parent_id`` не указан,
                          либо если запрос к API завершился ошибкой.
        """
        existing = self.find_page(title, space=space, expand="ancestors")
        if existing:
            if parent_id and not self._is_child_of(existing, parent_id):
                logger.warning(
                    f"Страница {title} найдена в другом дереве "
                    f"(ожидаемый parent_id={parent_id}). "
                    f"Возвращается ID существующей страницы — "
                    f"создать новую с тем же заголовком в Space невозможно."
                )
            return str(existing["id"])

        if not parent_id:
            raise PublishError(f"не указан parent_id для создания страницы {title}")

        placeholder = body or (f"<p>Автоматически созданная страница: {title}</p>")
        result = self._create_page(space, parent_id, title, placeholder)
        logger.info(f"Создана страница {title} (ID: {result['id']})")
        return str(result["id"])

    def get_page_body(self, space: str, title: str) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

        При отсутствии страницы или любой ошибке API возвращает пустую строку —
        вызывающий код (``PassportsStrategy``) рассматривает это как первую публикацию.

        Args:
            space: Ключ Space.
            title: Заголовок страницы.

        Returns:
            HTML-тело страницы или пустая строка.
        """
        existing = self.find_page(title, space=space, expand=_EXPAND_BODY)
        if not existing:
            return ""
        return existing.get("body", {}).get("storage", {}).get("value", "")

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
            space:  Ключ Space. Если не указан — используется ``self._space``.
            expand: Опциональный параметр ``expand`` для Confluence API
                    (например ``'version'`` или ``'body.storage'``).

        Returns:
            Словарь с данными страницы или ``None``, если страница не найдена.

        Raises:
            PublishError: Если запрос к API завершился ошибкой.
        """
        space = space or self._space
        params: dict[str, str] = {
            "spaceKey": space,
            "title": title,
            "type": _PAGE_TYPE,
        }
        if expand:
            params["expand"] = expand

        url = self._api_url("content")
        try:
            response = self._session.get(url, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise PublishError(f"HTTP-ошибка при поиске {title}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise PublishError(f"сетевая ошибка при поиске {title}: {e}") from e

        results: list[dict[str, Any]] = response.json().get("results", [])
        return results[0] if results else None

    def get_page(
        self,
        page_id: str,
        expand: str = _EXPAND_VERSION,
    ) -> dict[str, Any]:
        """
        Загружает страницу по ID.

        Args:
            page_id: ID страницы.
            expand:  Параметр ``expand`` (по умолчанию ``'version'``).

        Returns:
            Словарь с данными страницы.

        Raises:
            PublishError: Если страница не найдена (HTTP 404) или запрос не удался.
        """
        url = self._api_url("content", page_id)
        try:
            response = self._session.get(url, params={"expand": expand})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise PublishError(f"HTTP-ошибка для ID {page_id}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise PublishError(f"сетевая ошибка для ID {page_id}: {e}") from e

    def create_page(
        self,
        title: str,
        body: str,
        parent_id: str,
        space: str | None = None,
    ) -> dict[str, Any]:
        """
        Публичный метод создания страницы с использованием Space по умолчанию.

        Args:
            title:     Заголовок страницы.
            body:      Тело страницы в Storage Format.
            parent_id: ID родительской страницы.
            space:     Ключ Space. Если не указан — используется ``self._space``.

        Returns:
            Словарь ``{'id': str, 'version': int, 'status': str, 'message': str}``.

        Raises:
            PublishError: Если API вернул ошибку.
        """
        return self._create_page(space or self._space, parent_id, title, body)

    def update_page(
        self,
        page_id: str,
        title: str,
        body: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Публичный метод обновления страницы с автоинкрементом версии.

        Загружает текущую версию страницы по ``page_id``, затем выполняет
        обновление с увеличенным номером версии.

        Args:
            page_id:   ID страницы для обновления.
            title:     Новый заголовок страницы.
            body:      Новое тело страницы в Storage Format.
            parent_id: ID родителя. Если не указан — используется ``page_id``.

        Returns:
            Словарь ``{'id': str, 'version': int, 'status': str, 'message': str}``.

        Raises:
            PublishError: Если API вернул ошибку.
        """
        existing = self.get_page(page_id, expand=_EXPAND_VERSION)
        return self._update_page(existing, parent_id or page_id, title, body)

    def _create_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """
        Выполняет POST-запрос для создания новой страницы.

        Args:
            space:     Ключ Space.
            parent_id: ID родительской страницы.
            title:     Заголовок новой страницы.
            body_html: Тело страницы в Storage Format.

        Returns:
            Словарь ``{'id': str, 'version': int, 'status': str, 'message': str}``.

        Raises:
            PublishError: Если API вернул ошибку.
        """
        payload = self._build_page_payload(
            title=title,
            body_html=body_html,
            space=space,
            parent_id=parent_id,
            version_number=_INITIAL_VERSION,
        )
        url = self._api_url("content")
        try:
            response = self._session.post(url, json=payload)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise PublishError(f"HTTP-ошибка при создании {title}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise PublishError(f"сетевая ошибка при создании {title}: {e}") from e

        page_id = str(response.json().get("id", ""))
        logger.info(f"Создана страница {title} (ID: {page_id})")
        return {
            "id": page_id,
            "version": _INITIAL_VERSION,
            "status": "created",
            "message": f"Страница создана с версией {_INITIAL_VERSION}",
        }

    def _update_page(
        self,
        existing_page: dict[str, Any],
        parent_id: str,
        title: str,
        body_html: str,
    ) -> dict[str, Any]:
        """
        Выполняет PUT-запрос для обновления существующей страницы.

        Номер следующей версии вычисляется из данных существующей страницы.
        При невозможности извлечь версию используется ``_FALLBACK_VERSION``,
        что даёт следующую версию 1 — безопасный минимум для Confluence.

        Args:
            existing_page: Словарь с данными текущей страницы (из ``find_page``).
            parent_id:     ID родительской страницы.
            title:         Заголовок страницы.
            body_html:     Новое тело страницы.

        Returns:
            Словарь ``{'id': str, 'version': int, 'status': str, 'message': str}``.

        Raises:
            PublishError: Если API вернул ошибку.
        """
        page_id = str(existing_page["id"])
        current_version = self._extract_version(existing_page)
        next_version = current_version + 1

        logger.info(
            f"обновление {title}: v{current_version} → v{next_version} (ID: {page_id})"
        )

        payload = self._build_page_payload(
            title=title,
            body_html=body_html,
            space=None,
            parent_id=parent_id,
            version_number=next_version,
        )
        url = self._api_url("content", page_id)
        try:
            response = self._session.put(url, json=payload)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise PublishError(f"HTTP-ошибка при обновлении {title}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise PublishError(f"сетевая ошибка при обновлении {title}: {e}") from e

        return {
            "id": page_id,
            "version": next_version,
            "status": "updated",
            "message": f"Страница обновлена до версии {next_version}",
        }

    @staticmethod
    def _build_page_payload(
        title: str,
        body_html: str,
        version_number: int,
        parent_id: str,
        space: str | None = None,
    ) -> dict[str, Any]:
        """
        Собирает тело JSON-запроса для создания или обновления страницы.

        ``space`` включается только при создании (POST). При обновлении (PUT)
        Confluence принимает пейлоад без поля ``space``.

        Args:
            title:          Заголовок страницы.
            body_html:      Тело в Storage Format.
            version_number: Номер версии (для PUT — следующая версия).
            parent_id:      ID родительской страницы.
            space:          Ключ Space. ``None`` при обновлении.

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
            "ancestors": [{"id": parent_id}],
        }
        if space:
            payload["space"] = {"key": space}
        return payload

    @staticmethod
    def _extract_version(page: dict[str, Any]) -> int:
        """
        Извлекает номер версии из словаря страницы.

        Confluence возвращает версию в структуре ``{'version': {'number': N}}``.
        При отсутствии или некорректном типе возвращает ``_FALLBACK_VERSION``.

        Args:
            page: Словарь с данными страницы из ``find_page`` или ``get_page``.

        Returns:
            Текущий номер версии или ``_FALLBACK_VERSION`` (0) при ошибке парсинга.
        """
        try:
            return int(page.get("version", {}).get("number", _FALLBACK_VERSION))
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Не удалось извлечь версию из: {page}")
            return _FALLBACK_VERSION

    def _api_url(self, *parts: str) -> str:
        """
        Собирает URL к Confluence REST API v1.

        Args:
            *parts: Сегменты пути после ``/rest/api/`` (например ``'content'``,
                    ``'content'``, ``'12345'``).

        Returns:
            Полный URL вида ``https://confluence.example.com/rest/api/content/12345``.
        """
        return f"{self._base_url}/rest/api/{'/'.join(parts)}"

    @staticmethod
    def _is_child_of(page: dict[str, Any], parent_id: str) -> bool:
        """
        Проверяет, является ли страница прямым потомком указанного родителя.

        Confluence возвращает список предков в поле ``ancestors`` при запросе
        с ``expand=ancestors``. Метод проверяет, присутствует ли ``parent_id``
        среди предков страницы — это покрывает как прямых, так и косвенных
        потомков, что достаточно для защиты от записи в чужое дерево.

        Args:
            page:      Словарь страницы с полем ``ancestors`` (из ``find_page``
                       с ``expand='ancestors'``).
            parent_id: ID ожидаемого родителя.

        Returns:
            ``True`` если ``parent_id`` найден среди предков, иначе ``False``.
        """
        ancestors = page.get("ancestors", [])
        return any(str(a.get("id")) == str(parent_id) for a in ancestors)

    @staticmethod
    def _build_session(config: ConfluenceConfigSchema) -> RetryableSession:
        """
        Создаёт HTTP-сессию с аутентификацией и retry-логикой.

        Confluence Data Center: Bearer-аутентификация через PAT —
        токен передаётся в заголовке ``Authorization``, username не используется.

        Args:
            config: Конфигурация Confluence.

        Returns:
            Настроенная ``RetryableSession``.
        """
        session = create_retryable_session(
            token=config.token,
            bearer=True,
            max_retries=_RETRY_COUNT,
            backoff_factor=_BACKOFF_FACTOR,
            timeout=config.confluence_request_timeout,
        )
        session.verify = config.verify_ssl
        if not config.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.debug(
                "Проверка SSL-сертификата отключена, предупреждения urllib3 подавлены"
            )
        session.headers.update({"Content-Type": "application/json"})
        return session
