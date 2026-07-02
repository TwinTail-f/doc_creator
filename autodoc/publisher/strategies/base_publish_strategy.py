"""Абстрактный базовый класс стратегий публикации."""

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from jinja2 import TemplateError, TemplateNotFound

from autodoc.exceptions import ConfluenceError
from autodoc.models.parsed_result import ParsedResult

from autodoc.publisher.clients.confluence_client_protocol import ConfluenceClientProtocol
from autodoc.publisher.clients.models.page_result import PageResult
from autodoc.publisher.rendering.document_builder_protocol import DocumentBuilderProtocol
from autodoc.publisher.strategies.models.publish_report import PublishReport

from autodoc.common.logger import logger

_CDATA_PATTERN: re.Pattern[str] = re.compile(r"(<!\[CDATA\[.*?]]>)", re.DOTALL)


class BasePublishStrategy(ABC):
    """
    Абстрактная стратегия публикации документации в Confluence.

    Определяет общие зависимости и переиспользуемые шаги публикации
    (рендеринг шаблона, минификация HTML, обработка ошибок). Конкретный
    подкласс выбирается через ``autodoc.publisher.strategies.registry``.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClientProtocol,
        document_builder: DocumentBuilderProtocol,
        parsed_data: ParsedResult,
        space: str,
    ) -> None:
        """
        Инициализирует общие зависимости всех стратегий.

        Args:
            confluence_client: Реализация ``ConfluenceClientProtocol`` (обычно ``ConfluenceClient``).
            document_builder: Реализация ``DocumentBuilderProtocol`` (обычно ``DocumentBuilder``).
            parsed_data: Данные парсера (ParsedResult).
            space: Ключ Space в Confluence.

        Raises:
            ValueError: Если ``space`` пустой.
        """
        if not space:
            raise ValueError("space не может быть пустым")
        self._client = confluence_client
        self._builder = document_builder
        self._data = parsed_data
        self._space = space

    def _render_and_publish(
        self,
        page_title: str,
        template_name: str,
        view_model: dict[str, Any],
        parent_id: str | None,
    ) -> PageResult:
        """
        Рендерит шаблон и публикует страницу в Confluence.

        Args:
            page_title: Заголовок публикуемой страницы.
            template_name: Имя Jinja2-шаблона.
            view_model: Данные для рендеринга шаблона.
            parent_id: Идентификатор родительской страницы или None.

        Returns:
            Результат публикации в виде ``PageResult``.

        Raises:
            ConfluenceError: При сбое HTTP-запроса к Confluence.
            TemplateError: При ошибке рендеринга шаблона.
        """
        html_body = self._minify_html(self._builder.build(template_name, view_model))
        return self._client.publish_page(
            space=self._space,
            parent_id=parent_id,
            title=page_title,
            body_html=html_body,
        )

    def _publish_single_page(
        self,
        page_title: str,
        template_name: str,
        transform_fn: Callable[[], dict[str, Any]],
        parent_id: str,
        inject_links: Callable[[dict[str, Any]], None] | None = None,
    ) -> PublishReport:
        """
        Инкапсулирует общий поток публикации одной страницы для стратегий
        release и profile-centric.

        Args:
            page_title: Заголовок страницы Confluence для создания или обновления.
            template_name: Имя файла Jinja2-шаблона.
            transform_fn: Callable без аргументов, возвращающий словарь view-model.
            parent_id: ID родительской страницы Confluence (пустая строка = без родителя).
            inject_links: Опциональный callable, мутирующий view-model на месте.

        Returns:
            ``PublishReport`` с результатом попытки публикации.
        """
        errors: list[str] = []
        details: list[dict[str, Any]] = []

        try:
            view_model = transform_fn()
            if not view_model:
                raise ValueError("трансформер вернул пустой результат")

            view_model["space"] = self._space

            if inject_links is not None:
                inject_links(view_model)

            result = self._render_and_publish(
                page_title=page_title,
                template_name=template_name,
                view_model=view_model,
                parent_id=parent_id,
            )

            details.append(
                {
                    "page_title": page_title,
                    "page_id": result.id,
                    "version": result.version,
                    "status": result.status,
                    "template": template_name,
                }
            )
            logger.info(f"{page_title} {result.status} (ID: {result.id})")
            return PublishReport(success=True, pages_published=1, details=details)

        except (ConfluenceError, TemplateError, TemplateNotFound, ValueError, KeyError) as e:
            reason = str(e)
            errors.append(reason)
            logger.exception(f"Ошибка публикации {page_title}: {reason}")
            return PublishReport(
                success=False,
                pages_published=0,
                pages_failed=1,
                errors=errors,
                failed_pages=[{"page_title": page_title, "reason": reason}],
                details=details,
            )

    @staticmethod
    def _minify_html(html: str) -> str:
        """
        Минимизирует HTML-разметку перед публикацией в Confluence.

        Содержимое CDATA-блоков сохраняется без изменений.

        Args:
            html: Исходный HTML-текст шаблона.

        Returns:
            Минимизированный HTML без лишних пробелов и комментариев.
        """
        parts = _CDATA_PATTERN.split(html)
        result: list[str] = []
        for i, part in enumerate(parts):
            if i % 2 == 1:  # нечётные индексы — CDATA-блоки, сохраняем как есть
                result.append(part)
            else:
                part = re.sub(r"<!--.*?-->", "", part, flags=re.DOTALL)
                part = re.sub(r">\s+<", "><", part)
                part = re.sub(r"\s{2,}", " ", part)
                result.append(part)
        return "".join(result).strip()

    @abstractmethod
    def execute(self) -> PublishReport:
        """
        Выполняет стратегию публикации.

        Returns:
            ``PublishReport`` с результатами выполнения.
        """
