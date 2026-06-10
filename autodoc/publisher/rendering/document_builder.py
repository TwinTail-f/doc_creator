"""Рендеринг Jinja2-шаблонов в HTML Confluence Storage Format."""

import xml.sax.saxutils
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateNotFound

from autodoc.common.logger import logger


class DocumentBuilder:
    """
    Рендерит Jinja2-шаблоны в HTML для публикации в Confluence.

    Инициализирует окружение Jinja2 из директории ``rendering/`` и
    предоставляет единственный публичный метод ``build``.
    """

    def __init__(self, rendering_dir: Path) -> None:
        """
        Args:
            rendering_dir: Путь к директории ``rendering/`` (содержит
                ``templates/``, ``styles/``, ``macros/``). Корень
                ``FileSystemLoader`` устанавливается именно сюда, чтобы
                пути вида ``../styles/...`` и ``../macros/...`` внутри
                шаблонов корректно разрешались без выхода за пределы
                корня загрузчика.

        Raises:
            FileNotFoundError: Если директория не существует.
        """
        if not rendering_dir.exists():
            raise FileNotFoundError(
                f"Директория рендеринга не найдена: {rendering_dir}"
            )

        self._env: Environment = Environment(
            loader=FileSystemLoader(str(rendering_dir))
        )
        # Escape special XML characters in attribute values using the stdlib.
        # xml.sax.saxutils.escape handles & → &amp; and the extras dict adds " → &quot;.
        # Unlike manual str.replace, this avoids double-escaping already-escaped content.
        self._env.filters["xmlattr"] = (
            lambda s: xml.sax.saxutils.escape(str(s), {'"': '&quot;'})
        )
        logger.info(f"Инициализирован: {rendering_dir}")

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """
        Рендерит шаблон с переданными данными.

        Args:
            template_name: Имя файла шаблона (например ``'release_doc.jinja2'``).
            view_model: Словарь данных для передачи в шаблон (доступен
                        в шаблоне через переменную ``data``).

        Returns:
            HTML-строка в Confluence Storage Format.

        Raises:
            TemplateNotFound: Если шаблон не найден в директории.
            TemplateError: Если рендеринг завершился с ошибкой.
        """
        logger.debug(f'Рендеринг шаблона "{template_name}"')
        try:
            template = self._env.get_template(f"templates/{template_name}")
            html = template.render(data=view_model)
            logger.info(f'Шаблон "{template_name}" отрендерен')
            return html
        except (TemplateNotFound, TemplateError) as e:
            logger.error(f'Ошибка рендеринга "{template_name}": {e}')
            raise
