"""Клиент Confluence REST API v1."""

from typing import Any

from autodoc.publisher.clients.confluence_client_protocol import PageResult

import requests
import urllib3

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError
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
    Клиент для публикации и чтения страниц Confluence через REST API v1.

    Предназначен для использования стратегиями паблишера. Управляет
    жизненным циклом страниц: создаёт, обновляет и ищет их по заголовку
    и Space.

    Attributes:
        _base_url: Базовый URL Confluence без завершающего слеша.
        _space:    Ключ Space по умолчанию (используется во всех методах).
        _session:  HTTP-сессия с retry-логикой и аутентификацией.
    """

    def __init__(self, config: ConfluenceConfigSchema) -> None:
        """
        Создаёт клиент, готовый к работе с Confluence.

        Args:
            config: Валидированная конфигурация с URL, токеном и параметрами SSL.
        """
        self._base_url: str = config.url
        self._space: str = config.space
        self._session: RetryableSession = self._create_session(config)

        logger.debug(f"Инициализирован: {self._base_url} (space={self._space})")

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Публикует страницу в Confluence: создаёт новую или обновляет существующую.

        Если страница с таким заголовком найдена в дереве ``parent_id`` —
        обновляет её. Если отсутствует или принадлежит другому дереву —
        создаёт новую.

        Args:
            space:     Ключ Space в Confluence.
            parent_id: ID родительской страницы.
            title:     Заголовок страницы.
            body_html: Тело страницы в Confluence Storage Format (HTML).

        Returns:
            Результат операции в виде ``PageResult``.

        Raises:
            ConfluenceError: Если создание или обновление не удалось.
        """
        logger.info(f"Публикация страницы {title} (space={space})")

        existing = self._find_existing_page(
            title, space, parent_id, expand=f"{_EXPAND_VERSION},ancestors"
        )
        if existing:
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

        Если страница с таким заголовком найдена в дереве ``parent_id`` —
        возвращает её ID. Иначе создаёт новую страницу под ``parent_id``.

        Args:
            space:     Ключ Space.
            title:     Заголовок страницы.
            parent_id: ID родителя. Обязателен при создании новой страницы.
            body:      Тело новой страницы. Если пустое — вставляется заглушка.

        Returns:
            ID страницы в виде строки.

        Raises:
            ConfluenceError: Если страница не найдена и ``parent_id`` не указан,
                          либо если запрос к API завершился ошибкой.
        """
        existing = self._find_existing_page(title, space, parent_id)
        if existing:
            return str(existing["id"])

        if not parent_id:
            raise ConfluenceError(f"не указан parent_id для создания страницы {title}")

        placeholder = body or (f"<p>Автоматически созданная страница: {title}</p>")
        result = self._create_page(space, parent_id, title, placeholder)
        return str(result["id"])

    def get_page_body(self, space: str, title: str) -> str:
        """
        Возвращает тело страницы в Confluence Storage Format.

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
            expand: Параметр ``expand`` для Confluence API
                    (например ``'version'`` или ``'body.storage'``).

        Returns:
            Словарь с данными страницы или ``None``, если страница не найдена.

        Raises:
            ConfluenceError: Если запрос к API завершился ошибкой.
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
        response = self._request("GET", url, f"поиске страницы {title}", params=params)

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
            ConfluenceError: Если страница не найдена или запрос завершился ошибкой.
        """
        url = self._api_url("content", page_id)
        response = self._request(
            "GET", url, f"получении страницы {page_id}", params={"expand": expand}
        )
        return response.json()

    def _create_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Создаёт новую страницу в Confluence.

        Args:
            space:     Ключ Space.
            parent_id: ID родительской страницы.
            title:     Заголовок новой страницы.
            body_html: Тело страницы в Storage Format.

        Returns:
            Результат операции в виде ``PageResult``.

        Raises:
            ConfluenceError: Если API вернул ошибку.
        """
        payload = self._build_page_payload(
            title=title,
            body_html=body_html,
            space=space,
            parent_id=parent_id,
            version_number=_INITIAL_VERSION,
        )
        url = self._api_url("content")
        response = self._request("POST", url, f"создании {title}", json=payload)

        page_id = str(response.json().get("id", ""))
        logger.info(f"Создана страница {title} (ID: {page_id})")
        return PageResult(
            id=page_id,
            version=_INITIAL_VERSION,
            status="created",
            message=f"Страница создана с версией {_INITIAL_VERSION}",
        )

    def _update_page(
        self,
        existing_page: dict[str, Any],
        parent_id: str,
        title: str,
        body_html: str,
    ) -> PageResult:
        """
        Обновляет тело и версию существующей страницы в Confluence.

        Args:
            existing_page: Данные текущей страницы из ``find_page``.
            parent_id:     ID родительской страницы.
            title:         Заголовок страницы.
            body_html:     Новое тело страницы.

        Returns:
            Результат операции в виде ``PageResult``.

        Raises:
            ConfluenceError: Если API вернул ошибку.
        """
        page_id = str(existing_page["id"])
        current_version = self._extract_version(existing_page)
        next_version = current_version + 1

        logger.info(
            f"Обновление {title}: v{current_version} → v{next_version} (ID: {page_id})"
        )

        payload = self._build_page_payload(
            title=title,
            body_html=body_html,
            space=None,
            parent_id=parent_id,
            version_number=next_version,
        )
        url = self._api_url("content", page_id)
        self._request("PUT", url, f"обновлении {title}", json=payload)

        return PageResult(
            id=page_id,
            version=next_version,
            status="updated",
            message=f"Страница обновлена до версии {next_version}",
        )

    @staticmethod
    def _build_page_payload(
        title: str,
        body_html: str,
        version_number: int,
        parent_id: str,
        space: str | None = None,
    ) -> dict[str, Any]:
        """
        Формирует тело запроса к Confluence API для создания или обновления страницы.

        Args:
            title:          Заголовок страницы.
            body_html:      Тело в Storage Format.
            version_number: Номер версии (для PUT — следующая версия).
            parent_id:      ID родительской страницы.
            space:          Ключ Space. Передаётся только при создании, ``None`` при обновлении.

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
        Извлекает номер текущей версии страницы из ответа Confluence API.

        Args:
            page: Словарь с данными страницы.

        Returns:
            Номер версии или 0, если версия недоступна.
        """
        try:
            return int(page.get("version", {}).get("number", _FALLBACK_VERSION))
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Не удалось извлечь версию из: {page}")
            return _FALLBACK_VERSION

    def _request(
        self,
        method: str,
        url: str,
        action: str,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Выполняет HTTP-запрос к Confluence и возвращает ответ.

        Args:
            method: HTTP-метод (GET, POST, PUT и т.д.).
            url:      Целевой URL.
            action:   Описание действия для сообщения об ошибке (например, ``'поиске страницы'``).
            **kwargs: Дополнительные аргументы для ``requests.Session.request``.

        Returns:
            Ответ с проверенным статусом.

        Raises:
            ConfluenceError: При HTTP-ошибке или сетевом сбое.
        """
        try:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            raise ConfluenceError(f"HTTP-ошибка при {action}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ConfluenceError(f"Сетевая ошибка при {action}: {e}") from e

    def _api_url(self, *parts: str) -> str:
        """
        Строит URL к ресурсу Confluence REST API v1.

        Args:
            *parts: Сегменты пути после ``/rest/api/`` (например ``'content'``, ``'12345'``).

        Returns:
            Полный URL вида ``https://confluence.example.com/rest/api/content/12345``.
        """
        return f"{self._base_url}/rest/api/{'/'.join(parts)}"

    def _find_existing_page(
        self,
        title: str,
        space: str,
        parent_id: str | None,
        expand: str = "ancestors",
    ) -> dict[str, Any] | None:
        """
        Ищет страницу по заголовку в пределах указанного дерева.

        Args:
            title:     Заголовок страницы.
            space:     Ключ Space.
            parent_id: ID ожидаемого предка для проверки принадлежности дереву.
            expand:    Поля для раскрытия в ответе Confluence API.

        Returns:
            Словарь данных страницы или ``None``, если не найдена или в другом дереве.
        """
        existing = self.find_page(title, space=space, expand=expand)
        if existing and parent_id and not self._is_descendant_of(existing, parent_id):
            logger.warning(
                f"Страница {title} найдена в другом дереве "
                f"(ожидаемый parent_id={parent_id}), будет создана новая."
            )
            return None
        return existing

    @staticmethod
    def _is_descendant_of(page: dict[str, Any], parent_id: str) -> bool:
        """
        Проверяет, принадлежит ли страница дереву указанного предка.

        Args:
            page:      Словарь страницы с полем ``ancestors``.
            parent_id: ID ожидаемого предка.

        Returns:
            ``True``, если ``parent_id`` есть среди предков страницы, иначе ``False``.
        """
        ancestors = page.get("ancestors", [])
        return any(str(a.get("id")) == str(parent_id) for a in ancestors)

    @staticmethod
    def _create_session(config: ConfluenceConfigSchema) -> RetryableSession:
        """
        Создаёт и настраивает HTTP-сессию для работы с Confluence.

        Args:
            config: Конфигурация Confluence.

        Returns:
            Готовая к работе ``RetryableSession``.
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
