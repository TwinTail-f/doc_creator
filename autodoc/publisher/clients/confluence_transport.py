"""Низкоуровневый HTTP-транспорт для Confluence REST API v1."""

from typing import Any

import requests

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfluenceError
from autodoc.common.retryable_session import RetryableSession, create_bearer_session
from autodoc.common.logger import logger

_RETRY_COUNT: int = 3
_BACKOFF_FACTOR: float = 1.0


class ConfluenceTransport:
    """HTTP-клиент для взаимодействия с эндпоинтом ``/rest/api/content`` Confluence."""

    def __init__(self, config: ConfluenceConfigSchema) -> None:
        """
        Создаёт транспорт и инициализирует HTTP-сессию с переданной конфигурацией.

        Args:
            config: Валидированная конфигурация с URL, токеном и параметрами SSL.
        """
        self._base_url: str = config.url
        self._session: RetryableSession = self._create_session(config)

    def search_content(self, params: dict[str, str]) -> list[dict[str, Any]]:
        """
        Выполняет поиск страниц через GET ``/rest/api/content``.

        Args:
            params: Query-параметры (``spaceKey``, ``title``, ``type``, ``expand`` и т.д.).

        Returns:
            Список найденных страниц в сыром JSON-виде (может быть пустым).

        Raises:
            ConfluenceError: Если запрос завершился ошибкой.
        """
        response = self._request("GET", self._url(), "поиске страницы", params=params)
        results: list[dict[str, Any]] = response.json().get("results", [])
        return results

    def get_content(self, page_id: str, expand: str) -> dict[str, Any]:
        """
        Загружает страницу через GET ``/rest/api/content/{id}``.

        Args:
            page_id: ID страницы.
            expand: Параметр ``expand`` Confluence API.

        Returns:
            Сырой JSON страницы.

        Raises:
            ConfluenceError: Если страница не найдена или запрос завершился ошибкой.
        """
        response = self._request(
            "GET", self._url(page_id), f"получении страницы {page_id}", params={"expand": expand}
        )
        return response.json()

    def create_content(self, payload: dict[str, Any], title: str) -> dict[str, Any]:
        """
        Создаёт страницу через POST ``/rest/api/content``.

        Args:
            payload: Тело запроса (см. ``ConfluenceClient._build_payload``).
            title: Заголовок страницы — используется только в сообщении об ошибке.

        Returns:
            Сырой JSON созданной страницы.

        Raises:
            ConfluenceError: Если API вернул ошибку.
        """
        response = self._request("POST", self._url(), f"создании {title}", json=payload)
        return response.json()

    def update_content(self, page_id: str, payload: dict[str, Any], title: str) -> dict[str, Any]:
        """
        Обновляет страницу через PUT ``/rest/api/content/{id}``.

        Args:
            page_id: ID обновляемой страницы.
            payload: Тело запроса.
            title: Заголовок страницы — используется только в сообщении об ошибке.

        Returns:
            Сырой JSON обновлённой страницы.

        Raises:
            ConfluenceError: Если API вернул ошибку.
        """
        response = self._request("PUT", self._url(page_id), f"обновлении {title}", json=payload)
        return response.json()

    def _url(self, *parts: str) -> str:
        """Строит URL вида ``{base}/rest/api/content[/part1/part2...]``."""
        suffix = f"/{'/'.join(parts)}" if parts else ""
        return f"{self._base_url}/rest/api/content{suffix}"

    def _request(
        self,
        method: str,
        url: str,
        action: str,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Выполняет HTTP-запрос и преобразует сетевые и HTTP-ошибки в ``ConfluenceError``.

        Args:
            method: HTTP-метод (GET, POST, PUT и т.д.).
            url: Целевой URL.
            action: Описание действия для сообщения об ошибке
                    (например, ``'поиске страницы'``).
            **kwargs: Дополнительные аргументы для ``requests.Session.request``.

        Returns:
            Ответ с проверенным HTTP-статусом.

        Raises:
            ConfluenceError: При HTTP-ошибке или сетевом сбое.
        """
        try:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            detail = self._extract_error_detail(e.response)
            suffix = f" — {detail}" if detail else ""
            raise ConfluenceError(f"HTTP-ошибка при {action}: {e}{suffix}") from e
        except requests.exceptions.RequestException as e:
            raise ConfluenceError(f"Сетевая ошибка при {action}: {e}") from e

    @staticmethod
    def _extract_error_detail(response: requests.Response | None) -> str:
        """
        Извлекает человекочитаемое сообщение об ошибке из тела ответа Confluence.

        Args:
            response: Ответ сервера, либо ``None``, если ответа не было.

        Returns:
            Текст сообщения из поля ``message`` JSON-ответа, либо пустая строка,
            если тело отсутствует, не JSON, или поле ``message`` не найдено.
        """
        if response is None:
            return ""
        try:
            return str(response.json().get("message", ""))
        except (ValueError, AttributeError):
            return ""

    @staticmethod
    def _create_session(config: ConfluenceConfigSchema) -> RetryableSession:
        """
        Создаёт и настраивает HTTP-сессию для работы с Confluence.

        Args:
            config: Конфигурация Confluence.

        Returns:
            Готовая к работе ``RetryableSession`` с Bearer-аутентификацией.
        """
        session = create_bearer_session(
            token=config.token,
            max_retries=_RETRY_COUNT,
            backoff_factor=_BACKOFF_FACTOR,
            timeout=config.confluence_request_timeout,
        )
        session.verify = config.verify_ssl
        if not config.verify_ssl:
            logger.warning(
                "verify_ssl=False: проверка SSL-сертификата Confluence отключена. "
                "Соединение уязвимо к MITM-атакам — используйте это только для "
                "доверенной внутренней сети/тестового стенда. "
            )
        session.headers.update({"Content-Type": "application/json"})
        return session
