"""Рендеринг Jinja2-шаблонов в HTML Confluence Storage Format."""
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateNotFound

from autodoc.infrastructure.logger import logger


class DocumentBuilder:
    """
    Рендерит Jinja2-шаблоны в HTML для публикации в Confluence.

    Инициализирует окружение Jinja2 из указанной директории шаблонов
    и предоставляет единственный публичный метод ``build``.
    """

    def __init__(self, templates_dir: Path) -> None:
        """
        Args:
            templates_dir: Путь к директории с ``.jinja2``-шаблонами.

        Raises:
            FileNotFoundError: Если директория шаблонов не существует.
        """
        if not templates_dir.exists():
            raise FileNotFoundError(
                "Директория шаблонов не найдена: %s" % templates_dir
            )

        self._env: Environment = Environment(
            loader=FileSystemLoader(str(templates_dir))
        )
        logger.info("DocumentBuilder инициализирован: %s", templates_dir)

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
        logger.debug('рендеринг шаблона "%s"', template_name)
        try:
            template = self._env.get_template(template_name)
            html = template.render(data=view_model)
            logger.info('шаблон "%s" отрендерен', template_name)
            return html
        except (TemplateNotFound, TemplateError) as e:
            logger.error('DocumentBuilder: ошибка рендеринга "%s": %s', template_name, e)
            raise
